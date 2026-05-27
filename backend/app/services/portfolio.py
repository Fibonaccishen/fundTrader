from datetime import date
from decimal import Decimal

from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.holding import Holding
from ..models.transaction import Transaction
from ..models.nav_snapshot import NavSnapshot


async def get_latest_nav_for_fund(db: AsyncSession, fund_id: int) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    """Get latest (unit_nav, est_nav, daily_change_pct) for a fund."""
    result = await db.execute(
        select(NavSnapshot.unit_nav, NavSnapshot.est_nav, NavSnapshot.est_change_pct)
        .where(NavSnapshot.fund_id == fund_id)
        .order_by(NavSnapshot.nav_date.desc())
        .limit(1)
    )
    row = result.one_or_none()
    if row:
        return row[0], row[1], row[2]
    return None, None, None


async def get_yesterday_nav(db: AsyncSession, fund_id: int) -> Decimal | None:
    """Get yesterday's confirmed unit_nav (last trading day before today)."""
    today = date.today()
    result = await db.execute(
        select(NavSnapshot.unit_nav)
        .where(NavSnapshot.fund_id == fund_id)
        .where(NavSnapshot.unit_nav.isnot(None))
        .where(NavSnapshot.nav_date < today)
        .order_by(NavSnapshot.nav_date.desc())
        .limit(1)
    )
    nav = result.scalar_one_or_none()
    return nav


def calc_holding_pnl(holding: Holding, current_nav: Decimal | None) -> dict:
    """Calculate profit/loss for a holding given current NAV."""
    if current_nav is None or holding.total_shares == 0:
        market_value = Decimal("0")
    else:
        market_value = holding.total_shares * current_nav

    unrealized_pnl = market_value - holding.total_cost
    pnl_pct = Decimal("0")
    if holding.total_cost > 0:
        pnl_pct = (unrealized_pnl / holding.total_cost * 100).quantize(Decimal("0.01"))

    return {
        "market_value": market_value.quantize(Decimal("0.01")),
        "unrealized_pnl": unrealized_pnl.quantize(Decimal("0.01")),
        "pnl_pct": pnl_pct,
    }


async def get_dashboard_summary(db: AsyncSession) -> dict:
    """Aggregated portfolio summary."""
    result = await db.execute(
        select(Holding).where(Holding.status == "active")
    )
    holdings = result.scalars().all()

    total_cost = Decimal("0")
    total_market_value = Decimal("0")
    yesterday_market_value = Decimal("0")
    today_pnl = Decimal("0")
    top_gainer = None
    top_loser = None
    max_pnl_pct = Decimal("-999")
    min_pnl_pct = Decimal("999")

    for h in holdings:
        unit_nav, est_nav, est_change = await get_latest_nav_for_fund(db, h.fund_id)
        nav = est_nav or unit_nav
        pnl_info = calc_holding_pnl(h, nav)

        # Yesterday's NAV for yesterday P&L
        yesterday_nav = await get_yesterday_nav(db, h.fund_id)
        yesterday_pnl_info = calc_holding_pnl(h, yesterday_nav)

        total_cost += h.total_cost
        total_market_value += pnl_info["market_value"]
        yesterday_market_value += yesterday_pnl_info["market_value"]

        # Today's P&L: shares * (today's change in nav)
        if est_change is not None and nav is not None and est_change != Decimal("0"):
            prev_nav = nav / (Decimal("1") + est_change / Decimal("100"))
            day_change = nav - prev_nav
            today_pnl += (h.total_shares * day_change).quantize(Decimal("0.01"))

        pct = pnl_info["pnl_pct"]
        fund_info = {
            "fund_code": h.fund.code,
            "fund_name": h.fund.name,
            "pnl_pct": float(pct),
        }
        if pct > max_pnl_pct:
            max_pnl_pct = pct
            top_gainer = fund_info
        if pct < min_pnl_pct:
            min_pnl_pct = pct
            top_loser = fund_info

    total_unrealized_pnl = total_market_value - total_cost
    total_pnl_pct = Decimal("0")
    if total_cost > 0:
        total_pnl_pct = (total_unrealized_pnl / total_cost * 100).quantize(Decimal("0.01"))

    # Allocation data for pie charts
    strategy_allocation = {"long_term": Decimal("0"), "short_term": Decimal("0")}
    fund_allocation = []
    for h in holdings:
        unit_nav, est_nav, _ = await get_latest_nav_for_fund(db, h.fund_id)
        nav = est_nav or unit_nav
        mv = (h.total_shares * nav).quantize(Decimal("0.01")) if nav else Decimal("0")
        strategy_allocation[h.strategy_type or "long_term"] += mv
        fund_allocation.append({
            "name": h.fund.name,
            "code": h.fund.code,
            "strategy": h.strategy_type,
            "market_value": float(mv),
        })

    return {
        "total_cost": total_cost.quantize(Decimal("0.01")),
        "total_market_value": total_market_value.quantize(Decimal("0.01")),
        "yesterday_market_value": yesterday_market_value.quantize(Decimal("0.01")),
        "total_unrealized_pnl": total_unrealized_pnl.quantize(Decimal("0.01")),
        "yesterday_unrealized_pnl": (yesterday_market_value - total_cost).quantize(Decimal("0.01")),
        "total_pnl_pct": total_pnl_pct,
        "today_pnl": today_pnl,
        "holding_count": len(holdings),
        "top_gainer": top_gainer,
        "top_loser": top_loser if min_pnl_pct < 0 else None,
        "strategy_allocation": {
            "long_term": float(strategy_allocation["long_term"]),
            "short_term": float(strategy_allocation["short_term"]),
        },
        "fund_allocation": fund_allocation,
    }


async def update_holding_from_transactions(db: AsyncSession, holding: Holding):
    """Recalculate holding's total_shares/total_cost from its transactions."""
    result = await db.execute(
        select(
            func.sum(
                case(
                    (Transaction.transaction_type == "buy", Transaction.shares),
                    (Transaction.transaction_type == "sell", -Transaction.shares),
                )
            ),
            func.sum(
                case(
                    (Transaction.transaction_type == "buy", Transaction.amount + func.coalesce(Transaction.fee, 0)),
                    else_=0,
                )
            ),
        ).where(Transaction.holding_id == holding.id)
    )
    net_shares, total_buy_cost = result.one()
    holding.total_shares = net_shares or Decimal("0")
    holding.total_cost = total_buy_cost or Decimal("0")
    if holding.total_shares == 0:
        holding.status = "closed"
    await db.flush()
