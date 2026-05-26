from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.watchlist import WatchItem
from ..models.nav_snapshot import NavSnapshot
from ..services.fund_data import get_or_create_fund, fetch_realtime_estimation, fetch_fund_detail_online

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


class WatchItemCreate(BaseModel):
    fund_code: str
    notes: str | None = None


@router.get("")
async def list_watchlist(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WatchItem).order_by(WatchItem.added_at.desc()))
    items = result.scalars().all()

    output = []
    for w in items:
        # Get latest NAV and mini trend
        fund = await get_or_create_fund(db, w.fund_code)
        latest_nav = None
        nav_trend = []
        if fund:
            nav_result = await db.execute(
                select(NavSnapshot.nav_date, NavSnapshot.unit_nav)
                .where(NavSnapshot.fund_id == fund.id, NavSnapshot.unit_nav.isnot(None))
                .order_by(NavSnapshot.nav_date.desc()).limit(30)
            )
            nav_rows = nav_result.all()
            if nav_rows:
                latest_nav = float(nav_rows[0].unit_nav) if nav_rows[0].unit_nav else None
                nav_trend = [
                    {"date": str(r.nav_date), "nav": float(r.unit_nav) if r.unit_nav else 0}
                    for r in reversed(nav_rows)
                ]
            # If no NAV data, try fetch
            if not nav_rows:
                try:
                    from ..services.fund_data import fetch_and_save_nav
                    await fetch_and_save_nav(db, fund.id, fund.code)
                    nav_result = await db.execute(
                        select(NavSnapshot.nav_date, NavSnapshot.unit_nav)
                        .where(NavSnapshot.fund_id == fund.id, NavSnapshot.unit_nav.isnot(None))
                        .order_by(NavSnapshot.nav_date.desc()).limit(30)
                    )
                    nav_rows = nav_result.all()
                    if nav_rows:
                        latest_nav = float(nav_rows[0].unit_nav) if nav_rows[0].unit_nav else None
                        nav_trend = [
                            {"date": str(r.nav_date), "nav": float(r.unit_nav) if r.unit_nav else 0}
                            for r in reversed(nav_rows)
                        ]
                except Exception:
                    pass

        output.append({
            "id": w.id,
            "fund_code": w.fund_code,
            "fund_name": w.fund_name,
            "fund_type": w.fund_type,
            "notes": w.notes,
            "added_at": str(w.added_at),
            "latest_nav": latest_nav,
            "nav_trend": nav_trend,
        })
    return output


@router.post("", status_code=201)
async def add_to_watchlist(data: WatchItemCreate, db: AsyncSession = Depends(get_db)):
    # Check if already in watchlist
    exist = await db.execute(select(WatchItem).where(WatchItem.fund_code == data.fund_code))
    if exist.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Already in watchlist")

    # Get fund info
    fund = await get_or_create_fund(db, data.fund_code)
    if not fund:
        raise HTTPException(status_code=400, detail="Fund not found")

    item = WatchItem(
        fund_code=data.fund_code,
        fund_name=fund.name,
        fund_type=fund.fund_type,
        notes=data.notes,
    )
    db.add(item)
    await db.flush()
    return {"id": item.id, "message": "Added to watchlist"}


@router.delete("/{item_id}")
async def remove_from_watchlist(item_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WatchItem).where(WatchItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    await db.delete(item)
    await db.flush()
    return {"message": "Removed"}
