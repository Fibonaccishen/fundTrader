import json
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal

import httpx
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import HTTP_TIMEOUT
from ..database import async_session
from ..models.fund import Fund
from ..models.holding import Holding
from ..models.nav_snapshot import NavSnapshot
from ..models.market_data import MarketIndex, SectorData, FinancialNews, DailySummary
from ..services.fund_data import (
    fetch_realtime_estimation,
    fetch_fund_detail_online,
    fetch_and_save_nav,
    save_nav_snapshot,
)
from ..services.portfolio import get_dashboard_summary

logger = logging.getLogger("fundtrader.scheduler")

# Chinese holidays (approximate, can be updated)
CN_HOLIDAYS_2025 = {
    date(2025, 1, 1), date(2025, 1, 28), date(2025, 1, 29), date(2025, 1, 30),
    date(2025, 1, 31), date(2025, 4, 4), date(2025, 5, 1), date(2025, 5, 2),
    date(2025, 6, 2), date(2025, 10, 1), date(2025, 10, 2), date(2025, 10, 3),
}


def is_trading_day(d: date) -> bool:
    """Check if a date is a trading day (Mon-Fri, not a known holiday)."""
    if d.weekday() >= 5:
        return False
    if d in CN_HOLIDAYS_2025:
        return False
    return True


async def job_update_nav():
    """Update fund NAV data for all active holdings using pingzhongdata JS."""
    async with async_session() as db:
        result = await db.execute(select(Holding).where(Holding.status == "active"))
        holdings = result.scalars().all()
        fund_result = await db.execute(
            select(Fund).where(Fund.id.in_([h.fund_id for h in holdings]))
        )
        funds = {f.id: f for f in fund_result.scalars().all()}

        for holding in holdings:
            fund = funds.get(holding.fund_id)
            if not fund:
                continue
            try:
                await fetch_and_save_nav(db, fund.id, fund.code)
                logger.info(f"Updated NAV for {fund.code}")
            except Exception as e:
                logger.error(f"Failed to update NAV for {fund.code}: {e}")

        await db.commit()
    logger.info(f"NAV update completed for {len(holdings)} holdings")


async def job_update_realtime_nav():
    """Update real-time estimated NAV during trading hours."""
    now = datetime.now()
    if not is_trading_day(now.date()):
        return
    if now.hour < 9 or (now.hour == 9 and now.minute < 30) or now.hour > 15:
        return

    async with async_session() as db:
        result = await db.execute(select(Holding).where(Holding.status == "active"))
        holdings = result.scalars().all()
        fund_result = await db.execute(
            select(Fund).where(Fund.id.in_([h.fund_id for h in holdings]))
        )
        funds = {f.id: f for f in fund_result.scalars().all()}

        today = date.today()
        for holding in holdings:
            fund = funds.get(holding.fund_id)
            if not fund:
                continue
            try:
                est = await fetch_realtime_estimation(fund.code)
                if est:
                    gsz = est.get("gsz")
                    gszzl = est.get("gszzl")
                    await save_nav_snapshot(
                        db, fund.id, today,
                        est_nav=Decimal(str(gsz)) if gsz else None,
                        est_change_pct=Decimal(str(gszzl)) if gszzl else None,
                    )
            except Exception as e:
                logger.error(f"Failed to fetch real-time NAV for {fund.code}: {e}")
        await db.commit()


async def job_collect_market_indices():
    """Collect daily market index data."""
    if not is_trading_day(date.today()):
        return

    indices = {
        "1.000001": "上证指数",
        "0.399001": "深证成指",
        "0.399006": "创业板指",
        "1.000688": "科创50",
    }

    async with async_session() as db:
        for code, name in indices.items():
            try:
                data = await fetch_index_data(code)
                if data:
                    idx = MarketIndex(
                        index_code=code,
                        index_name=name,
                        record_date=date.today(),
                        close_price=data.get("close"),
                        change_pct=data.get("change_pct"),
                        open_price=data.get("open"),
                        high_price=data.get("high"),
                        low_price=data.get("low"),
                        volume=data.get("volume"),
                    )
                    db.add(idx)
            except Exception as e:
                logger.error(f"Failed to fetch index {code}: {e}")
        await db.commit()


async def fetch_index_data(code: str) -> dict | None:
    """Fetch index data from eastmoney API."""
    url = f"https://push2.eastmoney.com/api/qt/stock/get"
    params = {
        "secid": code,
        "fields": "f43,f44,f45,f46,f47,f48,f50,f57,f58,f169,f170",
        "ut": "fa5fd1943c7ff2bc7f404a7e64b8af18",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, timeout=HTTP_TIMEOUT)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if not data.get("data"):
            return None
        d = data["data"]
        return {
            "close": Decimal(str(d.get("f43", 0))) / 100 if d.get("f43") else None,
            "open": Decimal(str(d.get("f46", 0))) / 100 if d.get("f46") else None,
            "high": Decimal(str(d.get("f44", 0))) / 100 if d.get("f44") else None,
            "low": Decimal(str(d.get("f45", 0))) / 100 if d.get("f45") else None,
            "change_pct": Decimal(str(d.get("f170", 0))) / 100 if d.get("f170") else None,
            "volume": d.get("f47"),
        }


async def job_collect_sector_data():
    """Collect sector/industry plate performance data."""
    if not is_trading_day(date.today()):
        return

    hot_sectors = [
        ("BK0800", "AI人工智能"),
        ("BK0447", "半导体"),
        ("BK0478", "芯片"),
        ("BK0493", "新能源"),
        ("BK0465", "医药"),
        ("BK0448", "消费"),
        ("BK0481", "军工"),
    ]

    async with async_session() as db:
        for code, name in hot_sectors:
            try:
                data = await fetch_sector_data(code)
                if data:
                    sd = SectorData(
                        sector_name=name,
                        sector_code=code,
                        record_date=date.today(),
                        change_pct=data.get("change_pct"),
                        leading_funds=json.dumps(data.get("leading_funds", [])),
                    )
                    db.add(sd)
            except Exception as e:
                logger.error(f"Failed to fetch sector {name}: {e}")
        await db.commit()


async def fetch_sector_data(code: str) -> dict | None:
    """Fetch sector data from eastmoney."""
    url = f"https://push2.eastmoney.com/api/qt/stock/get"
    params = {
        "secid": f"90.{code}",
        "fields": "f43,f170",
        "ut": "fa5fd1943c7ff2bc7f404a7e64b8af18",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, timeout=HTTP_TIMEOUT)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if not data.get("data"):
            return None
        d = data["data"]
        return {
            "change_pct": Decimal(str(d.get("f170", 0))) / 100 if d.get("f170") else None,
            "leading_funds": [],
        }


async def job_collect_news():
    """Collect financial news headlines."""
    async with async_session() as db:
        try:
            news_list = await fetch_news()
            for n in news_list:
                existing = await db.execute(
                    select(FinancialNews).where(
                        FinancialNews.title == n["title"],
                        FinancialNews.source == n["source"],
                    )
                )
                if existing.scalar_one_or_none():
                    continue
                news = FinancialNews(
                    title=n["title"],
                    source=n["source"],
                    url=n.get("url"),
                    summary=n.get("summary"),
                    publish_time=n.get("publish_time"),
                    relevance_tags=json.dumps(n.get("tags", [])),
                )
                db.add(news)
            await db.commit()
        except Exception as e:
            logger.error(f"Failed to collect news: {e}")


async def fetch_news() -> list[dict]:
    """Fetch financial news headlines from Sina finance."""
    news_url = "https://feed.mix.sina.com.cn/api/roll/get"
    params = {"pageid": 153, "lid": 2509, "num": 20, "page": 1}
    headers = {"Referer": "https://finance.sina.com.cn/"}
    async with httpx.AsyncClient() as client:
        resp = await client.get(news_url, params=params, headers=headers, timeout=HTTP_TIMEOUT)
        if resp.status_code != 200:
            return []
        try:
            data = resp.json()
            items = data.get("result", {}).get("data", [])
            results = []
            tags_map = {
                "AI": ["AI", "人工智能", "大模型", "智能"],
                "芯片": ["芯片", "半导体", "集成电路"],
                "新能源": ["新能源", "光伏", "锂电", "储能"],
                "医药": ["医药", "医疗", "生物"],
            }
            for item in items:
                title = item.get("title", "")
                if not title:
                    continue
                tags = []
                for tag, keywords in tags_map.items():
                    if any(kw in title for kw in keywords):
                        tags.append(tag)
                ctime = item.get("ctime")
                if ctime:
                    try:
                        ctime_dt = datetime.fromtimestamp(int(ctime))
                    except (ValueError, TypeError):
                        ctime_dt = None
                else:
                    ctime_dt = None
                results.append({
                    "title": title,
                    "source": "新浪财经",
                    "url": item.get("url", ""),
                    "summary": item.get("intro", ""),
                    "publish_time": ctime_dt,
                    "tags": tags,
                })
            return results
        except Exception:
            return []


async def job_daily_summary():
    """Generate daily portfolio summary."""
    async with async_session() as db:
        try:
            summary_data = await get_dashboard_summary(db)
            existing = await db.execute(
                select(DailySummary).where(DailySummary.summary_date == date.today())
            )
            s = existing.scalar_one_or_none()
            if not s:
                s = DailySummary(summary_date=date.today())
                db.add(s)
            s.total_market_value = summary_data["total_market_value"]
            s.total_cost = summary_data["total_cost"]
            s.total_pnl = summary_data["total_unrealized_pnl"]
            s.pnl_pct = summary_data["total_pnl_pct"]
            await db.commit()
        except Exception as e:
            logger.error(f"Failed to generate daily summary: {e}")


async def job_cleanup():
    """Clean up old data."""
    async with async_session() as db:
        # Delete news older than 90 days
        cutoff_news = datetime.now() - timedelta(days=90)
        await db.execute(
            delete(FinancialNews).where(FinancialNews.collected_at < cutoff_news)
        )
        # Keep only last 365 days of NAV snapshots
        cutoff_nav = date.today() - timedelta(days=365)
        await db.execute(
            delete(NavSnapshot).where(NavSnapshot.nav_date < cutoff_nav)
        )
        await db.commit()
    logger.info("Data cleanup completed")
