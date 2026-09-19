"""Posting tasks: per-minute scheduler + single-post executor with retries.

Fully synchronous: no asyncio.run, no ThreadPoolExecutor, no event loop.
instagrapi calls are already blocking, so they run directly in the task.
"""
import datetime as dt
import logging
import random
import time

from app.tasks.celery_app import celery

log = logging.getLogger("igfunnel.tasks.post")


@celery.task(name="tasks.post_tasks.check_and_post", bind=True, max_retries=0)
def check_and_post(self):
    """Beat entry: create scheduled posts from due rules, then fire due posts."""
    from sqlalchemy import select

    from app.database import SyncSessionLocal
    from app.models import Post, PostStatus
    from app.tasks import sync_helpers as sched

    try:
        with SyncSessionLocal() as s:
            rules = sched.due_rules(s)
            created = 0
            used_video_ids: set[int] = set()
            for rule in rules:
                if sched.already_scheduled(s, rule):
                    continue
                account = sched.eligible_account(s, rule.account_id)
                if not account:
                    continue
                if not sched.account_reachable(s, account):
                    # Its proxy is down and no spare is healthy — leave the
                    # slot for the next tick instead of queueing a doomed post.
                    continue
                video = sched.next_video(s, rule.preferred_effect)
                if not video or video.id in used_video_ids:
                    continue
                if sched.video_already_queued(s, video.id):
                    # Queued by another rule (or the API) — one pending post
                    # per video, so it can never upload twice.
                    continue
                caption, _ = sched.pick_caption(s, rule.caption_template_id)
                tags = sched.pick_hashtags(s)
                # Â±5 min jitter
                when = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=random.randint(-5, 5))
                s.add(
                    Post(
                        video_id=video.id,
                        account_id=account.id,
                        caption=caption,
                        hashtags=tags,
                        status=PostStatus.scheduled,
                        scheduled_for=when,
                    )
                )
                s.flush()  # make the reservation visible to later rules in this tick
                s.commit()  # per-rule commit: one bad rule can't void the whole tick
                used_video_ids.add(video.id)
                created += 1

            now = dt.datetime.now(dt.timezone.utc)
            due = (
                s.execute(
                    select(Post).where(Post.status == PostStatus.scheduled, Post.scheduled_for <= now)
                )
            ).scalars().all()
            due_ids = [p.id for p in due]
            rule_count = len(rules)
        for pid in due_ids:
            execute_post.delay(pid)
        return {"rules_matched": rule_count, "created": created, "fired": len(due_ids)}
    except Exception:  # noqa: BLE001
        log.exception("check_and_post failed")
        return {"error": "tick failed"}


@celery.task(name="tasks.post_tasks.execute_post", bind=True, max_retries=3)
def execute_post(self, post_id: int):
    from celery.exceptions import Retry

    from app.config import settings
    from app.core.security import decrypt_secret
    from app.database import SyncSessionLocal
    from app.models import Account, AccountStatus, Post, PostStatus, Proxy, Video, VideoStatus
    from app.services.instagram_service import InstagramService
    from app.tasks import sync_helpers as sched
    from app.tasks.sync_helpers import log_event_sync, publish_sync
    from app.utils.instagram_helpers import session_path_for

    def set_status(status: PostStatus, **fields):
        with SyncSessionLocal() as s:
            post = s.get(Post, post_id)
            if not post:
                return
            post.status = status
            for k, v in fields.items():
                setattr(post, k, v)
            s.commit()
        publish_sync("post_status_update", {"post_id": post_id, "status": status.value})

    def touch_account(ok: bool, err: str = ""):
        with SyncSessionLocal() as s:
            post = s.get(Post, post_id)
            account = s.get(Account, post.account_id) if post else None
            if not account:
                return
            now = dt.datetime.now(dt.timezone.utc)
            note = ""
            if ok:
                account.last_post = now
                account.posts_today += 1
                account.total_posts += 1
            else:
                kind = err.split(":")[0]
                if kind == "challenge":
                    account.status = AccountStatus.challenge_required
                elif kind == "throttled":
                    from app.tasks.sync_helpers import throttle_cooldown_hours

                    hours = throttle_cooldown_hours(post.retry_count if post else 0)
                    account.status = AccountStatus.cooldown
                    account.cooldown_until = now + dt.timedelta(hours=hours)
                    # Throttling is usually IP-based: move to a spare proxy so
                    # the retry doesn't hammer the same flagged egress IP.
                    own = s.get(Proxy, account.proxy_id) if account.proxy_id else None
                    spare = sched.pick_spare_proxy(
                        s,
                        exclude_id=account.proxy_id,
                        prefer_country=own.country if own else None,
                    )
                    if spare is not None and spare.id != account.proxy_id:
                        account.proxy_id = spare.id
                        note = f" — rotated proxy, cooldown {hours}h"
                    else:
                        note = f" — no spare proxy, cooldown {hours}h"
            username = account.username
            s.commit()
            if note:
                log_event_sync("WARNING", "account", f"Account @{username} throttled{note}")

    try:
        # Single-flight claim: concurrent workers, beat redelivery and celery
        # retries can never upload the same post twice.
        with SyncSessionLocal() as s:
            outcome = sched.claim_post(s, post_id)
        if outcome == "missing":
            return {"post_id": post_id, "status": "missing"}
        if outcome == "busy":
            return {"post_id": post_id, "status": "already-handled"}
        publish_sync("post_status_update", {"post_id": post_id, "status": "posting"})

        with SyncSessionLocal() as s:
            post = s.get(Post, post_id)
            account = s.get(Account, post.account_id) if post else None
            video = s.get(Video, post.video_id) if post else None
            if post is None or account is None or video is None:
                # Stale references (account/video deleted after scheduling) —
                # fail the post explicitly instead of crashing on None.
                missing = [n for n, o in (("post", post), ("account", account), ("video", video)) if o is None]
                if post is not None:
                    post.status = PostStatus.failed
                    post.fail_reason = f"Stale reference: missing {', '.join(missing)}"
                    s.commit()
                publish_sync("post_status_update", {"post_id": post_id, "status": "failed"})
                return {"post_id": post_id, "status": "failed", "error": f"missing {', '.join(missing)}"}
            sibling = sched.find_blocking_sibling(s, post_id, video.id)
            if sibling is not None:
                # Another post row targets the same video and is in flight or
                # done — abort instead of double-uploading. Fail-closed: in the
                # narrow double-claim race both abort and the next tick
                # re-queues the video exactly once via the reservation.
                post.status = PostStatus.failed
                post.fail_reason = (
                    f"Superseded: video already handled by post #{sibling.id} ({sibling.status.value})"
                )
                s.commit()
                publish_sync("post_status_update", {"post_id": post_id, "status": "failed"})
                return {"post_id": post_id, "status": "failed", "error": "duplicate-superseded"}
            caption, tags, retries = post.caption, post.hashtags, post.retry_count
            video_id = video.id
            username, password = account.username, decrypt_secret(account.password_enc)
            video_path = video.processed_path or video.raw_path
            # Own proxy if healthy, else best spare (country-stable) — never
            # the raw name or a dead proxy.
            proxy_url = sched.resolve_proxy_url(s, account)

        # Anti-detection pre-post delay (blocking sleep — task is sync).
        time.sleep(random.uniform(settings.IG_PRE_POST_DELAY_MIN, settings.IG_PRE_POST_DELAY_MAX))

        # Re-verify after the sleep: the admin may have deleted the post or
        # moved it out of 'posting' while we waited — never upload then.
        with SyncSessionLocal() as s:
            post = s.get(Post, post_id)
            if post is None:
                return {"post_id": post_id, "status": "missing"}
            if post.status != PostStatus.posting:
                return {"post_id": post_id, "status": "already-handled"}

        svc = InstagramService(proxy_url=proxy_url, session_path=session_path_for(username, settings.MEDIA_ROOT))
        full_caption = (caption + "\n" + tags).strip()
        media_id, permalink, error = svc.upload_reel(username, password, video_path, full_caption)

        if error:
            kind = error.split(":")[0]
            if kind in ("throttled", "login_required") and retries < 3:
                # Park it back as scheduled (not failed) so the celery retry
                # re-claims it cleanly instead of tripping over a failed row.
                countdown = 2 ** retries * 60
                set_status(
                    PostStatus.scheduled,
                    fail_reason=error[:2000],
                    retry_count=retries + 1,
                    scheduled_for=dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=countdown),
                )
                touch_account(False, error)
                log_event_sync("ERROR", "post", f"Post {post_id} to @{username} failed: {error}")
                raise self.retry(exc=RuntimeError(error), countdown=countdown)
            set_status(PostStatus.failed, fail_reason=error[:2000], retry_count=retries + 1)
            touch_account(False, error)
            log_event_sync("ERROR", "post", f"Post {post_id} to @{username} failed: {error}")
            return {"post_id": post_id, "status": "failed", "error": error}

        set_status(
            PostStatus.posted,
            ig_media_id=media_id,
            ig_permalink=permalink,
            posted_at=dt.datetime.now(dt.timezone.utc),
        )
        touch_account(True)
        # Archive the video by captured id so it is never posted twice, even
        # if the post row itself was deleted in the meantime.
        with SyncSessionLocal() as s:
            v = s.get(Video, video_id)
            if v is not None and v.status != VideoStatus.posted:
                v.status = VideoStatus.posted
            s.commit()
        log_event_sync("INFO", "post", f"Posted to @{username}", {"post_id": post_id, "url": permalink})
        return {"post_id": post_id, "status": "posted", "url": permalink}
    except Retry:
        raise
    except Exception as exc:  # noqa: BLE001
        log.exception("execute_post %s failed", post_id)
        try:
            set_status(PostStatus.failed, fail_reason=str(exc)[:2000])
        except Exception:
            pass
        return {"post_id": post_id, "status": "failed", "error": str(exc)}
