from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field


# ----- Fund -----
class FundSearchResult(BaseModel):
    code: str
    name: str
    fund_type: str | None = None
    company: str | None = None


class FundDetail(BaseModel):
    code: str
    name: str
    fund_type: str | None = None
    company: str | None = None
    current_nav: Decimal | None = None
    est_nav: Decimal | None = None
    est_change_pct: Decimal | None = None
    nav_date: date | None = None


class NavHistoryItem(BaseModel):
    nav_date: date
    unit_nav: Decimal | None = None
    accumulated_nav: Decimal | None = None
    daily_change_pct: Decimal | None = None


# ----- Transaction -----
class TransactionCreate(BaseModel):
    fund_code: str
    transaction_type: str  # buy / sell
    transaction_date: date
    amount: Decimal = Field(gt=0)
    nav_at_purchase: Decimal = Field(gt=0)
    fee: Decimal = Field(default=0, ge=0)
    platform: str = "alipay"
    notes: str | None = None
    strategy_type: str = "long_term"  # long_term / short_term, used when creating new holding


class TransactionOut(BaseModel):
    id: int
    fund_id: int
    fund_code: str
    fund_name: str
    holding_id: int
    transaction_type: str
    transaction_date: date
    amount: Decimal
    nav_at_purchase: Decimal
    shares: Decimal
    fee: Decimal
    platform: str
    notes: str | None
    created_at: datetime


class TransactionUpdate(BaseModel):
    transaction_type: str | None = None
    transaction_date: date | None = None
    amount: Decimal | None = Field(default=None, gt=0)
    nav_at_purchase: Decimal | None = Field(default=None, gt=0)
    fee: Decimal | None = Field(default=None, ge=0)
    platform: str | None = None
    notes: str | None = None


# ----- Holding -----
class HoldingOut(BaseModel):
    id: int
    fund_code: str
    fund_name: str
    fund_type: str | None = None
    total_shares: Decimal
    total_cost: Decimal
    avg_cost_per_share: Decimal | None = None
    current_nav: Decimal | None = None
    est_nav: Decimal | None = None
    market_value: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    pnl_pct: Decimal | None = None
    daily_change_pct: Decimal | None = None
    strategy_type: str
    status: str
    notes: str | None = None


class HoldingUpdate(BaseModel):
    strategy_type: str | None = None
    notes: str | None = None
    status: str | None = None


# ----- Dashboard -----
class DashboardSummary(BaseModel):
    total_cost: Decimal
    total_market_value: Decimal
    total_unrealized_pnl: Decimal
    total_pnl_pct: Decimal
    today_pnl: Decimal
    holding_count: int
    remaining_cash: Decimal
    strategy_allocation: dict | None = None
    fund_allocation: list | None = None
    top_gainer: dict | None = None
    top_loser: dict | None = None


# ----- Market -----
class MarketIndexOut(BaseModel):
    index_code: str
    index_name: str
    record_date: date
    close_price: Decimal | None = None
    change_pct: Decimal | None = None


class SectorOut(BaseModel):
    sector_name: str
    sector_code: str | None = None
    record_date: date
    change_pct: Decimal | None = None


class NewsOut(BaseModel):
    title: str
    source: str | None = None
    url: str | None = None
    summary: str | None = None
    publish_time: datetime | None = None
    relevance_tags: str | None = None


# ----- Agent -----
class AgentPortfolioItem(BaseModel):
    fund_code: str
    fund_name: str
    fund_type: str | None = None
    total_shares: Decimal
    total_cost: Decimal
    avg_cost_per_share: Decimal | None = None
    current_nav: Decimal | None = None
    market_value: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    pnl_pct: Decimal | None = None
    daily_change_pct: Decimal | None = None
    strategy_type: str
    status: str


class AgentDailySummary(BaseModel):
    summary_date: date
    total_market_value: Decimal | None = None
    total_cost: Decimal | None = None
    total_pnl: Decimal | None = None
    pnl_pct: Decimal | None = None
    market_sentiment: str | None = None
    ai_notes: str | None = None


class AgentNotesCreate(BaseModel):
    summary_date: date
    market_sentiment: str | None = None
    ai_notes: str | None = None
