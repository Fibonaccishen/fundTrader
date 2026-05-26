from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import String, Date, DateTime, Numeric, Text, BigInteger, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base


class MarketIndex(Base):
    __tablename__ = "market_indices"
    __table_args__ = (UniqueConstraint("index_code", "record_date"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    index_code: Mapped[str] = mapped_column(String(20), nullable=False)
    index_name: Mapped[str] = mapped_column(String(100), nullable=False)
    record_date: Mapped[date] = mapped_column(Date, nullable=False)
    open_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    close_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    high_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    low_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    change_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    volume: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SectorData(Base):
    __tablename__ = "sector_data"
    __table_args__ = (UniqueConstraint("sector_code", "record_date"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sector_name: Mapped[str] = mapped_column(String(100), nullable=False)
    sector_code: Mapped[str | None] = mapped_column(String(20))
    record_date: Mapped[date] = mapped_column(Date, nullable=False)
    change_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    leading_funds: Mapped[str | None] = mapped_column(Text)  # JSON array
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class FinancialNews(Base):
    __tablename__ = "financial_news"
    __table_args__ = (UniqueConstraint("title", "source"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source: Mapped[str | None] = mapped_column(String(100))
    url: Mapped[str | None] = mapped_column(String(500))
    summary: Mapped[str | None] = mapped_column(Text)
    publish_time: Mapped[datetime | None] = mapped_column(DateTime)
    relevance_tags: Mapped[str | None] = mapped_column(Text)  # JSON array
    collected_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class DailySummary(Base):
    __tablename__ = "daily_summaries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    summary_date: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    total_market_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    total_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    total_pnl: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    pnl_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    market_sentiment: Mapped[str | None] = mapped_column(String(20))  # bullish/bearish/neutral
    ai_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
