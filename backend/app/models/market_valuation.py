from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import String, Date, DateTime, Numeric, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base


class MarketValuation(Base):
    __tablename__ = "market_valuation"
    __table_args__ = (UniqueConstraint("index_code", "val_date"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    index_code: Mapped[str] = mapped_column(String(20), nullable=False)
    index_name: Mapped[str] = mapped_column(String(100), nullable=False)
    val_date: Mapped[date] = mapped_column(Date, nullable=False)
    pe: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    pe_percentile: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))  # 历史分位 0-100
    pb: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    pb_percentile: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
