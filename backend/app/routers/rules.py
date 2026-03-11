from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import Rule, RuleEvent
from app.schemas import RuleCreate, RuleEventOut, RuleOut, RuleUpdate

router = APIRouter(prefix="/api/rules", tags=["rules"])


@router.get("", response_model=list[RuleOut])
async def list_rules(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Rule))
    return result.scalars().all()


@router.post("", response_model=RuleOut, status_code=201)
async def create_rule(body: RuleCreate, session: AsyncSession = Depends(get_session)):
    rule = Rule(
        name=body.name,
        enabled=body.enabled,
        condition_logic=body.condition_logic,
        conditions=[c.model_dump() for c in body.conditions],
        actions=[a.model_dump() for a in body.actions],
        on_clear_action=body.on_clear_action,
        on_clear_payload=body.on_clear_payload,
        cooldown_seconds=body.cooldown_seconds,
    )
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    return rule


@router.get("/events", response_model=list[RuleEventOut])
async def list_events(
    session: AsyncSession = Depends(get_session),
    rule_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=1000),
):
    query = select(RuleEvent).order_by(RuleEvent.timestamp.desc())
    if rule_id is not None:
        query = query.where(RuleEvent.rule_id == rule_id)
    query = query.limit(limit)
    result = await session.execute(query)
    return result.scalars().all()


@router.get("/{rule_id}", response_model=RuleOut)
async def get_rule(rule_id: int, session: AsyncSession = Depends(get_session)):
    rule = await session.get(Rule, rule_id)
    if not rule:
        raise HTTPException(404, "Rule not found")
    return rule


@router.put("/{rule_id}", response_model=RuleOut)
async def update_rule(rule_id: int, body: RuleUpdate, session: AsyncSession = Depends(get_session)):
    rule = await session.get(Rule, rule_id)
    if not rule:
        raise HTTPException(404, "Rule not found")
    rule.name = body.name
    rule.enabled = body.enabled
    rule.condition_logic = body.condition_logic
    rule.conditions = [c.model_dump() for c in body.conditions]
    rule.actions = [a.model_dump() for a in body.actions]
    rule.on_clear_action = body.on_clear_action
    rule.on_clear_payload = body.on_clear_payload
    rule.cooldown_seconds = body.cooldown_seconds
    await session.commit()
    await session.refresh(rule)
    return rule


@router.delete("/{rule_id}", status_code=204)
async def delete_rule(rule_id: int, session: AsyncSession = Depends(get_session)):
    rule = await session.get(Rule, rule_id)
    if not rule:
        raise HTTPException(404, "Rule not found")
    await session.execute(delete(Rule).where(Rule.id == rule_id))
    await session.commit()


@router.post("/{rule_id}/toggle", response_model=RuleOut)
async def toggle_rule(rule_id: int, session: AsyncSession = Depends(get_session)):
    rule = await session.get(Rule, rule_id)
    if not rule:
        raise HTTPException(404, "Rule not found")
    rule.enabled = not rule.enabled
    await session.commit()
    await session.refresh(rule)
    return rule
