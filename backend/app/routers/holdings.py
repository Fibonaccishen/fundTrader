from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.holding import Holding
from ..schemas.schemas import HoldingOut, HoldingUpdate
from ..services.portfolio import get_latest_nav_for_fund, calc_holding_pnl
from ..services.fund_data import fetch_realtime_estimation

router = APIRouter(prefix="/api/holdings", tags=["holdings"])


@router.get("", response_model=list[HoldingOut])
async def list_holdings(status: str = "active", db: AsyncSession = Depends(get_db)):
    """List all holdings with real-time P&L."""
    result = await db.execute(
        select(Holding).where(Holding.status == status)
    )
    holdings = result.scalars().all()

    output = []
    for h in holdings:
        unit_nav, est_nav, daily_change = await get_latest_nav_for_fund(db, h.fund_id)

        # Try real-time estimation from tiantian (only use estimate if no confirmed NAV yet)
        est = await fetch_realtime_estimation(h.fund.code)
        if est:
            gszzl = est.get("gszzl")
            if gszzl and not daily_change:
                daily_change = Decimal(str(gszzl))
            # Only use estimated NAV if we don't have a confirmed unit_nav for today
            if not unit_nav:
                gsz = est.get("gsz")
                if gsz:
                    est_nav = Decimal(str(gsz))

        current_nav = unit_nav or est_nav
        pnl = calc_holding_pnl(h, current_nav)

        avg_cost = None
        if h.total_shares > 0:
            avg_cost = (h.total_cost / h.total_shares).quantize(Decimal("0.0001"))

        output.append(HoldingOut(
            id=h.id,
            fund_code=h.fund.code,
            fund_name=h.fund.name,
            fund_type=h.fund.fund_type,
            total_shares=h.total_shares,
            total_cost=h.total_cost,
            avg_cost_per_share=avg_cost,
            current_nav=current_nav,
            est_nav=est_nav,
            market_value=pnl["market_value"],
            unrealized_pnl=pnl["unrealized_pnl"],
            pnl_pct=pnl["pnl_pct"],
            daily_change_pct=daily_change,
            strategy_type=h.strategy_type,
            status=h.status,
            notes=h.notes,
        ))

    return output


@router.patch("/{holding_id}", response_model=HoldingOut)
async def update_holding(holding_id: int, data: HoldingUpdate, db: AsyncSession = Depends(get_db)):
    """Update holding strategy type, notes, or status."""
    result = await db.execute(select(Holding).where(Holding.id == holding_id))
    holding = result.scalar_one_or_none()
    if not holding:
        raise HTTPException(status_code=404, detail="Holding not found")

    if data.strategy_type is not None:
        holding.strategy_type = data.strategy_type
    if data.notes is not None:
        holding.notes = data.notes
    if data.status is not None:
        holding.status = data.status
    await db.flush()

    unit_nav, est_nav, daily_change = await get_latest_nav_for_fund(db, holding.fund_id)
    current_nav = est_nav or unit_nav
    pnl = calc_holding_pnl(holding, current_nav)

    avg_cost = None
    if holding.total_shares > 0:
        avg_cost = (holding.total_cost / holding.total_shares).quantize(Decimal("0.0001"))

    return HoldingOut(
        id=holding.id,
        fund_code=holding.fund.code,
        fund_name=holding.fund.name,
        fund_type=holding.fund.fund_type,
        total_shares=holding.total_shares,
        total_cost=holding.total_cost,
        avg_cost_per_share=avg_cost,
        current_nav=current_nav,
        est_nav=est_nav,
        market_value=pnl["market_value"],
        unrealized_pnl=pnl["unrealized_pnl"],
        pnl_pct=pnl["pnl_pct"],
        daily_change_pct=daily_change,
        strategy_type=holding.strategy_type,
        status=holding.status,
        notes=holding.notes,
    )
