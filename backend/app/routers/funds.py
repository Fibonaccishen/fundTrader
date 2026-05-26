from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.fund import Fund
from ..models.nav_snapshot import NavSnapshot
from ..schemas.schemas import FundSearchResult, FundDetail, NavHistoryItem
from ..services.fund_data import (
    search_funds_online,
    get_or_create_fund,
    fetch_realtime_estimation,
    save_nav_history_to_db,
)

router = APIRouter(prefix="/api/funds", tags=["funds"])


@router.get("/search", response_model=list[FundSearchResult])
async def search_funds(keyword: str, db: AsyncSession = Depends(get_db)):
    """Search funds by code or name. Returns up to 20 results."""
    results = await search_funds_online(keyword)
    return results


@router.get("/{code}", response_model=FundDetail)
async def get_fund_detail(code: str, db: AsyncSession = Depends(get_db)):
    """Get fund detail with current NAV and real-time estimate."""
    fund = await get_or_create_fund(db, code)
    if not fund:
        raise HTTPException(status_code=404, detail="Fund not found")

    est_data = await fetch_realtime_estimation(code)

    return FundDetail(
        code=fund.code,
        name=fund.name,
        fund_type=fund.fund_type,
        company=fund.company,
        current_nav=est_data.get("dwjz") if est_data else None,
        est_nav=est_data.get("gsz") if est_data else None,
        est_change_pct=est_data.get("gszzl") if est_data else None,
        nav_date=est_data.get("jzrq") if est_data else None,
    )


@router.get("/{code}/nav-history", response_model=list[NavHistoryItem])
async def get_nav_history(code: str, days: int = 30, db: AsyncSession = Depends(get_db)):
    """Get historical NAV data for a fund. Returns from DB, fetching online if needed."""
    fund = await get_or_create_fund(db, code)
    if not fund:
        raise HTTPException(status_code=404, detail="Fund not found")

    result = await db.execute(
        select(NavSnapshot.unit_nav, NavSnapshot.accumulated_nav,
               NavSnapshot.daily_change_pct, NavSnapshot.nav_date)
        .where(NavSnapshot.fund_id == fund.id)
        .where(NavSnapshot.unit_nav.isnot(None))
        .order_by(NavSnapshot.nav_date.desc())
        .limit(days)
    )
    rows = result.all()

    if not rows:
        await save_nav_history_to_db(db, fund.id, code, days=days)
        result = await db.execute(
            select(NavSnapshot.unit_nav, NavSnapshot.accumulated_nav,
                   NavSnapshot.daily_change_pct, NavSnapshot.nav_date)
            .where(NavSnapshot.fund_id == fund.id)
            .where(NavSnapshot.unit_nav.isnot(None))
            .order_by(NavSnapshot.nav_date.desc())
            .limit(days)
        )
        rows = result.all()

    return [
        NavHistoryItem(
            nav_date=row.nav_date,
            unit_nav=row.unit_nav,
            accumulated_nav=row.accumulated_nav,
            daily_change_pct=row.daily_change_pct,
        )
        for row in reversed(rows)
    ]


@router.get("/{code}/nav-by-date")
async def get_nav_by_date(code: str, query_date: str, db: AsyncSession = Depends(get_db)):
    """Get NAV for a fund on a specific date. Falls back to nearest date if not found."""
    from datetime import date as date_type, timedelta
    from ..services.fund_data import fetch_and_save_nav
    fund = await get_or_create_fund(db, code)
    if not fund:
        raise HTTPException(status_code=404, detail="Fund not found")

    target = date_type.fromisoformat(query_date)

    # Check if fund has any NAV data at all; if not, fetch online first
    count_result = await db.execute(
        select(NavSnapshot).where(NavSnapshot.fund_id == fund.id).limit(1)
    )
    if not count_result.scalar_one_or_none():
        try:
            await fetch_and_save_nav(db, fund.id, fund.code)
        except Exception:
            pass

    # Try exact date first
    result = await db.execute(
        select(NavSnapshot)
        .where(NavSnapshot.fund_id == fund.id, NavSnapshot.nav_date == target)
        .where(NavSnapshot.unit_nav.isnot(None))
    )
    snap = result.scalar_one_or_none()

    # If not found, try nearby dates (search up to 5 days before/after)
    if not snap:
        for delta in range(1, 6):
            for d in [target - timedelta(days=delta), target + timedelta(days=delta)]:
                result = await db.execute(
                    select(NavSnapshot)
                    .where(NavSnapshot.fund_id == fund.id, NavSnapshot.nav_date == d)
                    .where(NavSnapshot.unit_nav.isnot(None))
                )
                snap = result.scalar_one_or_none()
                if snap:
                    break
            if snap:
                break

    if not snap:
        raise HTTPException(status_code=404, detail="No NAV data found near this date")

    return {
        "nav_date": str(snap.nav_date),
        "unit_nav": str(snap.unit_nav) if snap.unit_nav else None,
        "accumulated_nav": str(snap.accumulated_nav) if snap.accumulated_nav else None,
    }
