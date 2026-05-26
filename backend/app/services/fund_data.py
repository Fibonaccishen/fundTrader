import asyncio
from datetime import date
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import (
    TIANTIAN_REALTIME_URL,
    EASTMONEY_FUND_LIST_URL,
    EASTMONEY_FUND_DETAIL_URL,
    EASTMONEY_NAV_HISTORY_URL,
    HTTP_TIMEOUT,
    HTTP_MAX_CONCURRENT,
)
from ..utils.api_parser import (
    parse_jsonp,
    parse_fund_list_js,
    parse_fund_detail_js,
    safe_decimal,
    ms_timestamp_to_date,
)
from ..models.fund import Fund
from ..models.nav_snapshot import NavSnapshot

_semaphore = asyncio.Semaphore(HTTP_MAX_CONCURRENT)


async def _fetch(client: httpx.AsyncClient, url: str) -> str | None:
    async with _semaphore:
        try:
            resp = await client.get(url, timeout=HTTP_TIMEOUT)
            resp.raise_for_status()
            return resp.text
        except Exception:
            return None


async def search_funds_online(keyword: str) -> list[dict]:
    """Search funds by keyword from eastmoney fund list API. Caches results in DB."""
    async with httpx.AsyncClient() as client:
        text = await _fetch(client, EASTMONEY_FUND_LIST_URL)
        if not text:
            return []

    all_funds = parse_fund_list_js(text)
    kw = keyword.strip().lower()
    results = []
    for f in all_funds:
        if kw in f["code"] or kw in f["name"].lower():
            results.append(f)
        if len(results) >= 20:
            break
    return results


async def fetch_realtime_estimation(code: str) -> dict | None:
    """Fetch real-time estimated NAV from tiantian fund API.

    Returns dict with: fundcode, name, jzrq (NAV date), dwjz (unit NAV),
    gsz (estimated NAV), gszzl (estimated change %), gztime (estimate time).
    """
    url = TIANTIAN_REALTIME_URL.format(code=code)
    async with httpx.AsyncClient() as client:
        text = await _fetch(client, url)
        if not text:
            return None
    return parse_jsonp(text)


async def fetch_fund_detail_online(code: str) -> dict | None:
    """Fetch detailed fund data from eastmoney pingzhongdata JS."""
    url = EASTMONEY_FUND_DETAIL_URL.format(code=code)
    headers = {"Referer": "https://fundf10.eastmoney.com/"}
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=headers, timeout=HTTP_TIMEOUT)
            if resp.status_code != 200:
                return None
            return parse_fund_detail_js(resp.text)
        except Exception:
            return None


async def fetch_nav_history(code: str, page_size: int = 30) -> list[dict]:
    """Fetch historical NAV records from eastmoney API.

    Each record: FSRQ (date), DWJZ (unit NAV), LJJZ (accumulated NAV), JZZZL (change %).
    """
    url = f"{EASTMONEY_NAV_HISTORY_URL}?fundCode={code}&pageIndex=1&pageSize={page_size}"
    headers = {"Referer": "https://fundf10.eastmoney.com/"}
    async with httpx.AsyncClient() as client:
        text = await _fetch_headers(client, url, headers)
        if not text:
            return []
    data = parse_jsonp(text)
    if not data or "Data" not in data or "LSJZList" not in data["Data"]:
        return []
    return data["Data"]["LSJZList"]


async def _fetch_headers(client: httpx.AsyncClient, url: str, headers: dict) -> str | None:
    async with _semaphore:
        try:
            resp = await client.get(url, headers=headers, timeout=HTTP_TIMEOUT)
            resp.raise_for_status()
            return resp.text
        except Exception:
            return None


async def get_or_create_fund(db: AsyncSession, code: str) -> Fund | None:
    """Get fund from DB or create it from online data. Falls back to search if detail fails."""
    result = await db.execute(select(Fund).where(Fund.code == code))
    fund = result.scalar_one_or_none()
    if fund:
        return fund

    detail = await fetch_fund_detail_online(code)
    if detail and detail.get("name"):
        fund = Fund(
            code=code,
            name=detail.get("name", code),
            fund_type=detail.get("fund_type"),
            company=detail.get("company"),
        )
    else:
        # Fallback: search for the fund code online
        results = await search_funds_online(code)
        match = None
        for r in results:
            if r["code"] == code:
                match = r
                break
        if not match:
            return None
        fund = Fund(
            code=code,
            name=match.get("name", code),
            fund_type=match.get("fund_type"),
            company=match.get("company"),
        )
    db.add(fund)
    await db.flush()
    return fund


async def save_nav_snapshot(
    db: AsyncSession, fund_id: int, nav_date: date,
    unit_nav: Decimal | None = None,
    accumulated_nav: Decimal | None = None,
    daily_change_pct: Decimal | None = None,
    est_nav: Decimal | None = None,
    est_change_pct: Decimal | None = None,
):
    """Insert or update a NAV snapshot for a fund on a given date."""
    result = await db.execute(
        select(NavSnapshot).where(
            NavSnapshot.fund_id == fund_id,
            NavSnapshot.nav_date == nav_date,
        )
    )
    snap = result.scalar_one_or_none()

    if snap:
        if unit_nav is not None:
            snap.unit_nav = unit_nav
        if accumulated_nav is not None:
            snap.accumulated_nav = accumulated_nav
        if daily_change_pct is not None:
            snap.daily_change_pct = daily_change_pct
        if est_nav is not None:
            snap.est_nav = est_nav
        if est_change_pct is not None:
            snap.est_change_pct = est_change_pct
    else:
        snap = NavSnapshot(
            fund_id=fund_id,
            nav_date=nav_date,
            unit_nav=unit_nav,
            accumulated_nav=accumulated_nav,
            daily_change_pct=daily_change_pct,
            est_nav=est_nav,
            est_change_pct=est_change_pct,
        )
        db.add(snap)
    await db.flush()


async def save_nav_history_to_db(db: AsyncSession, fund_id: int, code: str, days: int = 30):
    """Fetch historical NAV for a fund and save to database."""
    records = await fetch_nav_history(code, page_size=days)
    for r in records:
        try:
            nav_date_str = r.get("FSRQ", "")
            if not nav_date_str:
                continue
            nav_date = date.fromisoformat(nav_date_str)
            unit_nav = safe_decimal(r.get("DWJZ"))
            acc_nav = safe_decimal(r.get("LJJZ"))
            change_pct_str = r.get("JZZZL", "0")
            change_pct = safe_decimal(change_pct_str.replace("%", "")) if change_pct_str else None
            await save_nav_snapshot(
                db, fund_id, nav_date,
                unit_nav=unit_nav,
                accumulated_nav=acc_nav,
                daily_change_pct=change_pct,
            )
        except (ValueError, KeyError):
            continue


async def get_latest_nav(db: AsyncSession, fund_id: int) -> NavSnapshot | None:
    """Get the most recent NAV snapshot for a fund."""
    result = await db.execute(
        select(NavSnapshot)
        .where(NavSnapshot.fund_id == fund_id)
        .order_by(NavSnapshot.nav_date.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def fetch_and_save_nav(db: AsyncSession, fund_id: int, code: str):
    """Fetch NAV data from pingzhongdata JS and save to DB. Used on first fund creation."""
    detail = await fetch_fund_detail_online(code)
    if detail and "nav_trend" in detail:
        from ..utils.api_parser import ms_timestamp_to_date, safe_decimal
        for point in detail["nav_trend"]:
            try:
                x = point.get("x")
                if not x:
                    continue
                nav_date = ms_timestamp_to_date(x)
                unit_nav = safe_decimal(point.get("y"))
                eq = point.get("equityReturn", 0)
                change_pct = safe_decimal(eq) if eq != 0 else None
                result = await db.execute(
                    select(NavSnapshot).where(NavSnapshot.fund_id == fund_id, NavSnapshot.nav_date == nav_date)
                )
                existing = result.scalar_one_or_none()
                if existing:
                    if not existing.unit_nav:
                        existing.unit_nav = unit_nav
                    if change_pct is not None and existing.daily_change_pct is None:
                        existing.daily_change_pct = change_pct
                else:
                    db.add(NavSnapshot(fund_id=fund_id, nav_date=nav_date, unit_nav=unit_nav, daily_change_pct=change_pct))
            except Exception:
                continue
        await db.flush()
    # Also get latest from tiantian
    est = await fetch_realtime_estimation(code)
    if est and est.get("dwjz"):
        from ..utils.api_parser import safe_decimal as sd
        jzrq = est.get("jzrq")
        try:
            nd = date.fromisoformat(jzrq)
        except (ValueError, TypeError):
            nd = date.today()
        await save_nav_snapshot(db, fund_id, nd, unit_nav=sd(est.get("dwjz")), est_nav=sd(est.get("gsz")) if est.get("gsz") else None, est_change_pct=sd(est.get("gszzl")) if est.get("gszzl") else None)
