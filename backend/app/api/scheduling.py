"""Schedule rules, captions, hashtag sets."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_db
from app.models import CaptionTemplate, HashtagSet, ScheduleRule
from app.schemas.content import (
    CaptionIn, CaptionOut, HashtagSetIn, HashtagSetOut, ScheduleRuleIn, ScheduleRuleOut,
)

schedule_router = APIRouter()
caption_router = APIRouter()
hashtag_router = APIRouter()


def _rule_out(r: ScheduleRule) -> ScheduleRuleOut:
    return ScheduleRuleOut(
        id=r.id, name=r.name, day_of_week=r.day_of_week, hour=r.hour, minute=r.minute,
        account_id=r.account_id, is_active=r.is_active, preferred_effect=r.preferred_effect,
        caption_template_id=r.caption_template_id, created_at=r.created_at,
    )


@schedule_router.get("", response_model=list[ScheduleRuleOut])
async def list_rules(_: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(ScheduleRule).order_by(ScheduleRule.hour, ScheduleRule.minute))).scalars().all()
    return [_rule_out(r) for r in rows]


@schedule_router.post("", response_model=ScheduleRuleOut, status_code=201)
async def create_rule(body: ScheduleRuleIn, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    # SQLite doesn't enforce FKs — validate here so rules can't orphan.
    from app.models import Account, CaptionTemplate

    if body.account_id is not None and await db.get(Account, body.account_id) is None:
        raise HTTPException(404, "Account not found")
    if body.caption_template_id is not None and await db.get(CaptionTemplate, body.caption_template_id) is None:
        raise HTTPException(404, "Caption template not found")
    r = ScheduleRule(**body.model_dump())
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return _rule_out(r)


@schedule_router.put("/{rule_id}", response_model=ScheduleRuleOut)
async def update_rule(rule_id: int, body: ScheduleRuleIn, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    r = await db.get(ScheduleRule, rule_id)
    if not r:
        raise HTTPException(404, "Rule not found")
    for k, v in body.model_dump().items():
        setattr(r, k, v)
    await db.commit()
    await db.refresh(r)
    return _rule_out(r)


@schedule_router.delete("/{rule_id}", status_code=204)
async def delete_rule(rule_id: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    r = await db.get(ScheduleRule, rule_id)
    if not r:
        raise HTTPException(404, "Rule not found")
    await db.delete(r)
    await db.commit()
    return None


@schedule_router.post("/{rule_id}/toggle")
async def toggle_rule(rule_id: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    r = await db.get(ScheduleRule, rule_id)
    if not r:
        raise HTTPException(404, "Rule not found")
    r.is_active = not r.is_active
    await db.commit()
    return {"is_active": r.is_active}


@schedule_router.get("/calendar/data")
async def calendar(_: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select as sel

    from app.models import Post, PostStatus

    rules = (await db.execute(select(ScheduleRule))).scalars().all()
    upcoming = (
        await db.execute(
            sel(Post).where(Post.status == PostStatus.scheduled).order_by(Post.scheduled_for.asc()).limit(200)
        )
    ).scalars().all()
    return {
        "rules": [_rule_out(r).model_dump() for r in rules],
        "upcoming": [{"id": p.id, "account_id": p.account_id, "scheduled_for": p.scheduled_for} for p in upcoming],
    }


# ---- Captions ----

@caption_router.get("", response_model=list[CaptionOut])
async def list_captions(_: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(CaptionTemplate).order_by(CaptionTemplate.name))).scalars().all()
    return [CaptionOut(id=c.id, name=c.name, content=c.content, category=c.category, is_active=c.is_active, use_count=c.use_count, avg_engagement=c.avg_engagement) for c in rows]


@caption_router.post("", response_model=CaptionOut, status_code=201)
async def create_caption(body: CaptionIn, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    c = CaptionTemplate(**body.model_dump())
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return CaptionOut(id=c.id, name=c.name, content=c.content, category=c.category, is_active=c.is_active, use_count=c.use_count, avg_engagement=c.avg_engagement)


@caption_router.put("/{cid}", response_model=CaptionOut)
async def update_caption(cid: int, body: CaptionIn, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    c = await db.get(CaptionTemplate, cid)
    if not c:
        raise HTTPException(404, "Caption not found")
    for k, v in body.model_dump().items():
        setattr(c, k, v)
    await db.commit()
    await db.refresh(c)
    return CaptionOut(id=c.id, name=c.name, content=c.content, category=c.category, is_active=c.is_active, use_count=c.use_count, avg_engagement=c.avg_engagement)


@caption_router.delete("/{cid}", status_code=204)
async def delete_caption(cid: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    c = await db.get(CaptionTemplate, cid)
    if not c:
        raise HTTPException(404, "Caption not found")
    await db.delete(c)
    await db.commit()
    return None


@caption_router.get("/{cid}/performance")
async def caption_performance(cid: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    from sqlalchemy import func

    from app.models import Post, PostStatus

    c = await db.get(CaptionTemplate, cid)
    if not c:
        raise HTTPException(404, "Caption not found")
    # Approximate: posts whose caption matches this template exactly.
    row = (
        await db.execute(
            select(func.count(Post.id), func.avg(Post.engagement_rate), func.coalesce(func.sum(Post.views_7d), 0)).where(
                Post.caption == c.content, Post.status == PostStatus.posted
            )
        )
    ).one()
    return {"use_count": c.use_count, "matched_posts": row[0], "avg_engagement": round(float(row[1] or 0), 2), "total_views": int(row[2] or 0)}


# ---- Hashtags ----

@hashtag_router.get("", response_model=list[HashtagSetOut])
async def list_tags(_: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(HashtagSet).order_by(HashtagSet.name))).scalars().all()
    return [HashtagSetOut(id=h.id, name=h.name, tags=h.tags, is_active=h.is_active, use_count=h.use_count) for h in rows]


@hashtag_router.post("", response_model=HashtagSetOut, status_code=201)
async def create_tags(body: HashtagSetIn, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    h = HashtagSet(**body.model_dump())
    db.add(h)
    await db.commit()
    await db.refresh(h)
    return HashtagSetOut(id=h.id, name=h.name, tags=h.tags, is_active=h.is_active, use_count=h.use_count)


@hashtag_router.put("/{hid}", response_model=HashtagSetOut)
async def update_tags(hid: int, body: HashtagSetIn, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    h = await db.get(HashtagSet, hid)
    if not h:
        raise HTTPException(404, "Hashtag set not found")
    for k, v in body.model_dump().items():
        setattr(h, k, v)
    await db.commit()
    await db.refresh(h)
    return HashtagSetOut(id=h.id, name=h.name, tags=h.tags, is_active=h.is_active, use_count=h.use_count)


@hashtag_router.delete("/{hid}", status_code=204)
async def delete_tags(hid: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    h = await db.get(HashtagSet, hid)
    if not h:
        raise HTTPException(404, "Hashtag set not found")
    await db.delete(h)
    await db.commit()
    return None
