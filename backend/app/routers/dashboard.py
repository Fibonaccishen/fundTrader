from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.market_data import DailySummary, MarketIndex, SectorData
from ..models.user_settings import UserSettings
from ..models.holding import Holding
from ..models.market_valuation import MarketValuation
from ..models.nav_snapshot import NavSnapshot
from ..schemas.schemas import DashboardSummary, MarketIndexOut, SectorOut
from ..services.portfolio import get_dashboard_summary, get_latest_nav_for_fund

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
async def dashboard_summary(db: AsyncSession = Depends(get_db)):
    """Get aggregated portfolio summary with remaining cash."""
    summary_data = await get_dashboard_summary(db)
    # Calculate remaining cash
    settings_result = await db.execute(select(UserSettings).limit(1))
    settings = settings_result.scalar_one_or_none()
    total_capital = settings.total_capital if settings else Decimal("0")
    holdings_result = await db.execute(select(Holding).where(Holding.status == "active"))
    holdings = holdings_result.scalars().all()
    total_invested = sum((h.total_cost for h in holdings), Decimal("0"))
    remaining = total_capital - total_invested
    summary_data["remaining_cash"] = remaining
    return summary_data


@router.get("/risk-analysis")
async def risk_analysis(db: AsyncSession = Depends(get_db)):
    """Analyze portfolio concentration risk."""
    from ..models.holding import Holding
    result = await db.execute(select(Holding).where(Holding.status == "active"))
    holdings = result.scalars().all()

    if not holdings:
        return {"concentration": [], "warnings": [], "total_market_value": 0}

    # Sector keyword mapping
    sector_keywords = {
        "半导体/芯片": ["半导体", "芯片", "科创"],
        "AI/人工智能": ["AI", "人工智能", "智能"],
        "新能源": ["新能源", "光伏", "锂电", "储能", "碳中和"],
        "消费/白酒": ["消费", "白酒", "食品", "饮料"],
        "医药/医疗": ["医药", "医疗", "生物", "健康"],
        "纳斯达克/QDII": ["纳斯达克", "标普", "QDII", "全球"],
        "宽基指数": ["沪深300", "中证500", "上证50", "创业板", "科创50"],
        "其他": [],
    }

    sector_values = {}
    total_mv = Decimal("0")
    detail = []

    for h in holdings:
        unit_nav, est_nav, _ = await get_latest_nav_for_fund(db, h.fund_id)
        nav = est_nav or unit_nav
        mv = h.total_shares * nav if nav else Decimal("0")
        total_mv += mv

        name = h.fund.name or ""
        ftype = h.fund.fund_type or ""
        matched = "其他"
        for sector, keywords in sector_keywords.items():
            if sector == "其他":
                continue
            if any(kw in name or kw in ftype for kw in keywords):
                matched = sector
                break
        sector_values[matched] = sector_values.get(matched, Decimal("0")) + mv
        detail.append({
            "name": name, "code": h.fund.code,
            "sector": matched, "market_value": float(mv),
        })

    concentration = [
        {"sector": s, "market_value": float(v), "pct": round(float(v / total_mv * 100), 1) if total_mv > 0 else 0}
        for s, v in sorted(sector_values.items(), key=lambda x: x[1], reverse=True)
    ]

    warnings = []
    for c in concentration:
        if c["pct"] > 50:
            warnings.append({"level": "danger", "msg": f"板块「{c['sector']}」占比{c['pct']}%，过度集中！建议分散到其他板块"})
        elif c["pct"] > 30:
            warnings.append({"level": "warning", "msg": f"板块「{c['sector']}」占比{c['pct']}%，偏高，留意风险"})
    if not warnings:
        warnings.append({"level": "success", "msg": "持仓板块分布较为分散，未发现明显集中风险"})

    return {"concentration": concentration, "warnings": warnings, "detail": detail, "total_market_value": float(total_mv)}


@router.get("/pnl-trend")
async def pnl_trend(days: int = 30, db: AsyncSession = Depends(get_db)):
    """Get daily P&L trend data."""
    result = await db.execute(
        select(DailySummary)
        .order_by(DailySummary.summary_date.desc())
        .limit(days)
    )
    summaries = result.scalars().all()
    return [
        {
            "date": str(s.summary_date),
            "total_market_value": float(s.total_market_value) if s.total_market_value else 0,
            "total_cost": float(s.total_cost) if s.total_cost else 0,
            "total_pnl": float(s.total_pnl) if s.total_pnl else 0,
            "pnl_pct": float(s.pnl_pct) if s.pnl_pct else 0,
        }
        for s in reversed(summaries)
    ]


@router.get("/market-indices", response_model=list[MarketIndexOut])
async def market_indices(days: int = 1, db: AsyncSession = Depends(get_db)):
    """Get recent market index data."""
    # Get latest date
    subq = select(MarketIndex.record_date).order_by(MarketIndex.record_date.desc()).limit(days)
    result = await db.execute(
        select(MarketIndex).where(MarketIndex.record_date.in_(subq.scalar_subquery()))
        .order_by(MarketIndex.record_date.desc(), MarketIndex.index_code)
    )
    indices = result.scalars().all()
    return [
        MarketIndexOut(
            index_code=m.index_code,
            index_name=m.index_name,
            record_date=m.record_date,
            close_price=m.close_price,
            change_pct=m.change_pct,
        )
        for m in indices
    ]


@router.get("/sectors", response_model=list[SectorOut])
async def sectors(days: int = 1, db: AsyncSession = Depends(get_db)):
    """Get recent sector performance data."""
    subq = select(SectorData.record_date).order_by(SectorData.record_date.desc()).limit(days)
    result = await db.execute(
        select(SectorData).where(SectorData.record_date.in_(subq.scalar_subquery()))
        .order_by(SectorData.record_date.desc(), SectorData.change_pct.desc())
    )
    sectors = result.scalars().all()
    return [
        SectorOut(
            sector_name=s.sector_name,
            sector_code=s.sector_code,
            record_date=s.record_date,
            change_pct=s.change_pct,
        )
        for s in sectors
    ]


@router.get("/market-valuation")
async def market_valuation(db: AsyncSession = Depends(get_db)):
    """Get latest PE/PB valuation for major indices."""
    # Get latest valuation for each index
    indices = ["000300", "000905", "399006"]
    result = []
    for code in indices:
        row_result = await db.execute(
            select(MarketValuation)
            .where(MarketValuation.index_code == code)
            .order_by(MarketValuation.val_date.desc())
            .limit(1)
        )
        v = row_result.scalar_one_or_none()
        if v:
            status = "normal"
            if v.pe_percentile:
                p = float(v.pe_percentile)
                if p < 30: status = "undervalued"
                elif p > 70: status = "overvalued"
            result.append({
                "index_code": v.index_code,
                "index_name": v.index_name,
                "val_date": str(v.val_date),
                "pe": float(v.pe) if v.pe else None,
                "pe_percentile": float(v.pe_percentile) if v.pe_percentile else None,
                "pb": float(v.pb) if v.pb else None,
                "pb_percentile": float(v.pb_percentile) if v.pb_percentile else None,
                "status": status,
            })

    # If no data, seed with estimates and retry
    if not result:
        await _seed_valuation(db)
        for code in indices:
            row_result = await db.execute(
                select(MarketValuation)
                .where(MarketValuation.index_code == code)
                .order_by(MarketValuation.val_date.desc())
                .limit(1)
            )
            v = row_result.scalar_one_or_none()
            if v:
                result.append({
                    "index_code": v.index_code, "index_name": v.index_name,
                    "val_date": str(v.val_date),
                    "pe": float(v.pe) if v.pe else None,
                    "pe_percentile": float(v.pe_percentile) if v.pe_percentile else None,
                    "pb": float(v.pb) if v.pb else None,
                    "pb_percentile": float(v.pb_percentile) if v.pb_percentile else None,
                    "status": "normal",
                })
    return result


async def _seed_valuation(db: AsyncSession):
    """Seed initial PE valuation data with known approximate values."""
    today = date.today()
    seeds = [
        ("000300", "沪深300", today, 12.5, 45.0, 1.35, 35.0),
        ("000905", "中证500", today, 28.0, 75.0, 2.10, 60.0),
        ("399006", "创业板指", today, 35.0, 50.0, 4.80, 55.0),
    ]
    for code, name, d, pe, pep, pb, pbp in seeds:
        db.add(MarketValuation(
            index_code=code, index_name=name, val_date=d,
            pe=Decimal(str(pe)), pe_percentile=Decimal(str(pep)),
            pb=Decimal(str(pb)), pb_percentile=Decimal(str(pbp)),
        ))
    await db.flush()


@router.get("/daily-pnl-detail")
async def daily_pnl_detail(query_date: str, db: AsyncSession = Depends(get_db)):
    """Get per-fund daily P&L breakdown for a specific date."""
    from datetime import date as date_type, timedelta
    target = date_type.fromisoformat(query_date)

    # Find previous trading day with NAV data
    prev_result = await db.execute(
        select(NavSnapshot.nav_date)
        .where(NavSnapshot.nav_date < target, NavSnapshot.unit_nav.isnot(None))
        .order_by(NavSnapshot.nav_date.desc())
        .limit(1)
    )
    prev_date_row = prev_result.scalar_one_or_none()

    result = await db.execute(select(Holding).where(Holding.status == "active"))
    holdings = result.scalars().all()

    details = []
    total_daily_pnl = Decimal("0")

    # Build shares history for accurate per-date calculation
    from ..models.transaction import Transaction
    txn_result = await db.execute(select(Transaction).order_by(Transaction.transaction_date))
    all_txns = txn_result.scalars().all()
    fund_shares_history = {}
    for h in holdings:
        fund_shares_history[h.fund_id] = []
    for t in all_txns:
        if t.fund_id in fund_shares_history:
            prev = fund_shares_history[t.fund_id][-1][1] if fund_shares_history[t.fund_id] else Decimal("0")
            new_s = prev + t.shares if t.transaction_type == "buy" else prev - t.shares
            fund_shares_history[t.fund_id].append((t.transaction_date, new_s))

    def get_shares(fid, d):
        hist = fund_shares_history.get(fid, [])
        s = Decimal("0")
        for dt, sh in hist:
            if dt <= d: s = sh
            else: break
        return s

    for h in holdings:
        today_nav_result = await db.execute(
            select(NavSnapshot.unit_nav)
            .where(NavSnapshot.fund_id == h.fund_id, NavSnapshot.nav_date == target)
        )
        today_nav = today_nav_result.scalar_one_or_none()

        yesterday_nav = None
        if prev_date_row:
            prev_nav_result = await db.execute(
                select(NavSnapshot.unit_nav)
                .where(NavSnapshot.fund_id == h.fund_id, NavSnapshot.nav_date == prev_date_row)
            )
            yesterday_nav = prev_nav_result.scalar_one_or_none()

        if today_nav and yesterday_nav:
            shares_ytd = get_shares(h.fund_id, prev_date_row)
            if shares_ytd > 0:
                daily_pnl = (shares_ytd * (today_nav - yesterday_nav)).quantize(Decimal("0.01"))
                total_daily_pnl += daily_pnl
                details.append({
                    "fund_code": h.fund.code,
                    "fund_name": h.fund.name,
                    "shares": float(shares_ytd),
                    "today_nav": float(today_nav),
                    "yesterday_nav": float(yesterday_nav),
                    "daily_pnl": float(daily_pnl),
                })

    return {
        "date": query_date,
        "total_daily_pnl": float(total_daily_pnl),
        "details": sorted(details, key=lambda x: abs(x["daily_pnl"]), reverse=True),
    }


@router.get("/daily-pnl-calendar")
async def daily_pnl_calendar(year: int, month: int, db: AsyncSession = Depends(get_db)):
    """Get daily P&L for a calendar month view. Calculated from NAV data directly."""
    import calendar
    from datetime import date as date_type, timedelta

    start = date_type(year, month, 1)
    end = date_type(year, month, calendar.monthrange(year, month)[1])

    # Get all active holdings
    result = await db.execute(select(Holding).where(Holding.status == "active"))
    holdings = result.scalars().all()
    fund_ids = [h.fund_id for h in holdings]

    if not fund_ids:
        days = [{"date": str(start + timedelta(days=i)), "pnl": None, "market_value": None, "pnl_pct": None} for i in range((end - start).days + 1)]
        return {"year": year, "month": month, "days": days, "month_summary": {"total_pnl": 0, "positive_days": 0, "negative_days": 0, "best_day": None, "worst_day": None}}

    # Build historical shares for each fund by date
    from ..models.transaction import Transaction
    txn_result = await db.execute(select(Transaction).order_by(Transaction.transaction_date))
    all_txns = txn_result.scalars().all()
    fund_shares_history = {}
    for h in holdings:
        fund_shares_history[h.fund_id] = []
    for t in all_txns:
        if t.fund_id in fund_shares_history:
            prev = fund_shares_history[t.fund_id][-1][1] if fund_shares_history[t.fund_id] else Decimal("0")
            new_shares = prev + t.shares if t.transaction_type == "buy" else prev - t.shares
            fund_shares_history[t.fund_id].append((t.transaction_date, new_shares))

    def get_shares_on_date(fund_id: int, target_date: date) -> Decimal:
        history = fund_shares_history.get(fund_id, [])
        if not history:
            return Decimal("0")
        shares = Decimal("0")
        for d, s in history:
            if d <= target_date: shares = s
            else: break
        return shares

    # Calculate daily P&L PER FUND using each fund's own trading dates
    # Then aggregate to get daily total
    daily_pnl_map: dict[date, Decimal] = {}
    for h in holdings:
        # Get this fund's NAV dates in range
        nav_dates_result = await db.execute(
            select(NavSnapshot.nav_date)
            .where(NavSnapshot.fund_id == h.fund_id, NavSnapshot.unit_nav.isnot(None))
            .where(NavSnapshot.nav_date >= start - timedelta(days=10), NavSnapshot.nav_date <= end)
            .order_by(NavSnapshot.nav_date)
        )
        fund_dates = [r for r in nav_dates_result.scalars().all()]

        for i in range(1, len(fund_dates)):
            today = fund_dates[i]
            yesterday = fund_dates[i - 1]
            # Get NAVs
            tn_result = await db.execute(
                select(NavSnapshot.unit_nav).where(NavSnapshot.fund_id == h.fund_id, NavSnapshot.nav_date == today)
            )
            yn_result = await db.execute(
                select(NavSnapshot.unit_nav).where(NavSnapshot.fund_id == h.fund_id, NavSnapshot.nav_date == yesterday)
            )
            tn = tn_result.scalar_one_or_none()
            yn = yn_result.scalar_one_or_none()
            if tn and yn:
                shares = get_shares_on_date(h.fund_id, yesterday)
                if shares > 0:
                    fund_daily = shares * (tn - yn)
                    daily_pnl_map[today] = daily_pnl_map.get(today, Decimal("0")) + fund_daily

    # Quantize all values
    for d in daily_pnl_map:
        daily_pnl_map[d] = daily_pnl_map[d].quantize(Decimal("0.01"))

    # Find first transaction date
    first_txn_date = None
    if all_txns:
        first_txn_date = all_txns[0].transaction_date

    # Collect all unique NAV dates (trading days for any holding)
    all_nav_dates = set()
    for h in holdings:
        nav_dates_result = await db.execute(
            select(NavSnapshot.nav_date)
            .where(NavSnapshot.fund_id == h.fund_id, NavSnapshot.unit_nav.isnot(None))
            .where(NavSnapshot.nav_date >= start, NavSnapshot.nav_date <= end)
        )
        all_nav_dates.update(r for r in nav_dates_result.scalars().all())

    # Build calendar days - only show data from first transaction date
    days = []
    d = start
    while d <= end:
        has_holdings = first_txn_date and d >= first_txn_date
        if d in daily_pnl_map:
            days.append({"date": str(d), "pnl": float(daily_pnl_map[d]), "market_value": None, "pnl_pct": None})
        elif d in all_nav_dates and has_holdings:
            # Trading day with NAV but no daily delta (first day of holdings)
            days.append({"date": str(d), "pnl": 0.0, "market_value": None, "pnl_pct": None})
        else:
            days.append({"date": str(d), "pnl": None, "market_value": None, "pnl_pct": None})
        d += timedelta(days=1)

    trading_days = [d for d in days if d["pnl"] is not None]
    month_pnl = sum((Decimal(str(d["pnl"])) for d in trading_days), Decimal("0"))
    positive = sum(1 for d in trading_days if d["pnl"] > 0)
    negative = sum(1 for d in trading_days if d["pnl"] < 0)

    return {
        "year": year, "month": month,
        "days": days,
        "month_summary": {
            "total_pnl": float(month_pnl),
            "positive_days": positive,
            "negative_days": negative,
            "best_day": max(trading_days, key=lambda x: x["pnl"], default=None) if trading_days else None,
            "worst_day": min(trading_days, key=lambda x: x["pnl"], default=None) if trading_days else None,
        },
    }
