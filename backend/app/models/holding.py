from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, DateTime, Numeric, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..database import Base


class Holding(Base):
    __tablename__ = "holdings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    fund_id: Mapped[int] = mapped_column(ForeignKey("funds.id"), nullable=False)
    total_shares: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active / closed
    strategy_type: Mapped[str] = mapped_column(String(20), default="long_term")  # long_term / short_term
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    fund = relationship("Fund", lazy="joined")
    transactions = relationship("Transaction", back_populates="holding", lazy="selectin")
