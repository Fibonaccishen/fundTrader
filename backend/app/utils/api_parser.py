import re
import json
from decimal import Decimal
from datetime import date, datetime
from typing import Any


def parse_jsonp(text: str, callback_name: str = "") -> dict | None:
    """Parse JSONP response like `jsonpgz({...})` or `callback({...})`."""
    pattern = r'[\w.]*\((\{.*\})\)'
    if callback_name:
        pattern = re.escape(callback_name) + r'\((\{.*\})\)'
    m = re.search(pattern, text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def parse_fund_list_js(text: str) -> list[dict]:
    """Parse `var r = [[...],[...]];` from eastmoney fundcode_search.js."""
    m = re.search(r'var\s+r\s*=\s*(\[\[.*?\]\]);', text, re.DOTALL)
    if not m:
        return []
    try:
        rows = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []
    results = []
    for row in rows:
        if len(row) >= 5:
            results.append({
                "code": str(row[0]),
                "name": str(row[2]),
                "fund_type": str(row[3]),
                "company": str(row[4]) if len(row) > 4 else "",
            })
    return results


def parse_js_var(text: str, var_name: str) -> Any:
    """Parse a JS variable assignment like `var Data_netWorthTrend = [...];`."""
    # Strip BOM if present
    clean = text.lstrip("﻿")
    pattern = r'var\s+' + re.escape(var_name) + r'\s*=\s*(.*?);'
    m = re.search(pattern, clean, re.DOTALL)
    if not m:
        return None
    raw = m.group(1).strip()
    # Handle JS null
    if raw == "null":
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def parse_fund_detail_js(text: str) -> dict:
    """Parse eastmoney pingzhongdata JS and extract all useful data."""
    result: dict = {}

    name = parse_js_var(text, "fS_name")
    if name:
        result["name"] = name

    code = parse_js_var(text, "fS_code")
    if code:
        result["code"] = code

    fund_type = parse_js_var(text, "fS_typename")
    if fund_type:
        result["fund_type"] = fund_type

    company = parse_js_var(text, "fS_companyname")
    if company:
        result["company"] = company

    # NAV trend data: [{x: ms_timestamp, y: nav, equityReturn: ..., unitMoney: ...}, ...]
    nav_trend = parse_js_var(text, "Data_netWorthTrend")
    if nav_trend:
        result["nav_trend"] = nav_trend

    # Accumulated NAV trend
    acc_nav_trend = parse_js_var(text, "Data_ACWorthTrend")
    if acc_nav_trend:
        result["acc_nav_trend"] = acc_nav_trend

    return result


def parse_eastmoney_nav_jsonp(text: str) -> dict | None:
    """Parse historical NAV JSONP from api.fund.eastmoney.com/f10/lsjz."""
    return parse_jsonp(text)


def safe_decimal(value, default="0") -> Decimal:
    """Safely convert any value to Decimal, return default on failure."""
    if value is None or value == "" or value == "-":
        return Decimal(default)
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal(default)


def ms_timestamp_to_date(ms: int) -> date:
    """Convert millisecond timestamp to date."""
    return datetime.fromtimestamp(ms / 1000).date()
