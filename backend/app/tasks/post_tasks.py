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
            for rule in rules:
                if sched.already_scheduled(s, rule):
                    continue
                account = sched.eligible_account(s, rule.account_id)
                video = sched.next_video(s, rule.preferred_effect)
                if not account or not video:
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
                created += 1
            s.commit()

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
    from app.config import settings
    from app.core.security import decrypt_secret
    from app.database import SyncSessionLocal
    from app.models import Account, AccountStatus, Post, PostStatus, Proxy, Video, VideoStatus
    from app.services.instagram_service import InstagramService
    from app.services.proxy_service import proxy_url_for
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
            if ok:
                account.last_post = now
                account.posts_today += 1
                account.total_posts += 1
            else:
                kind = err.split(":")[0]
                if kind == "challenge":
                    account.status = AccountStatus.challenge_required
                elif kind == "throttled":
                    account.status = AccountStatus.cooldown
                    account.cooldown_until = now + dt.timedelta(hours=24)
            s.commit()

    try:
        with SyncSessionLocal() as s:
            post = s.get(Post, post_id)
            if not post:
                return {"post_id": post_id, "status": "missing"}
            account = s.get(Account, post.account_id)
            video = s.get(Video, post.video_id)
            proxy = s.get(Proxy, account.proxy_id) if account and account.proxy_id else None
            caption, tags, retries = post.caption, post.hashtags, post.retry_count
            username, password = account.username, decrypt_secret(account.password_enc)
            video_path = video.processed_path or video.raw_path
            proxy_url = proxy_url_for(proxy) if proxy else None

        set_status(PostStatus.posting)

        # Anti-detection pre-post delay (blocking sleep â€” task is sync).
        time.sleep(random.uniform(settings.IG_PRE_POST_DELAY_MIN, settings.IG_PRE_POST_DELAY_MAX))

        svc = InstagramService(proxy_url=proxy_url, session_path=session_path_for(username, settings.MEDIA_ROOT))
        full_caption = (caption + "\n" + tags).strip()
        media_id, permalink, error = svc.upload_reel(username, password, video_path, full_caption)

        if error:
            kind = error.split(":")[0]
            set_status(PostStatus.failed, fail_reason=error[:2000], retry_count=retries + 1)
            touch_account(False, error)
            log_event_sync("ERROR", "post", f"Post {post_id} to @{username} failed: {error}")
            if kind in ("throttled", "login_required") and retries < 3:
                raise self.retry(exc=RuntimeError(error), countdown=2 ** retries * 60)
            return {"post_id": post_id, "status": "failed", "error": error}

        set_status(
            PostStatus.posted,
            ig_media_id=media_id,
            ig_permalink=permalink,
            posted_at=dt.datetime.now(dt.timezone.utc),
        )
        touch_account(True)
        # Archive the video so it is never posted twice.
        with SyncSessionLocal() as s:
            post = s.get(Post, post_id)
            if post:
                v = s.get(Video, post.video_id)
                if v:
                    v.status = VideoStatus.posted
                s.commit()
        log_event_sync("INFO", "post", f"Posted to @{username}", {"post_id": post_id, "url": permalink})
        return {"post_id": post_id, "status": "posted", "url": permalink}
    except Exception as exc:  # noqa: BLE001
        log.exception("execute_post %s failed", post_id)
        try:
            set_status(PostStatus.failed, fail_reason=str(exc)[:2000])
        except Exception:
            pass
        return {"post_id": post_id, "status": "failed", "error": str(exc)}
