from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import Date, DateTime, Numeric, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base


class NavSnapshot(Base):
    __tablename__ = "nav_snapshots"
    __table_args__ = (UniqueConstraint("fund_id", "nav_date"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    fund_id: Mapped[int] = mapped_column(ForeignKey("funds.id"), nullable=False)
    nav_date: Mapped[date] = mapped_column(Date, nullable=False)
    unit_nav: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    accumulated_nav: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    daily_change_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    est_nav: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    est_change_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    est_time: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
