from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import String, Date, DateTime, Numeric, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    fund_id: Mapped[int] = mapped_column(ForeignKey("funds.id"), nullable=False)
    holding_id: Mapped[int] = mapped_column(ForeignKey("holdings.id"), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(10), nullable=False)  # buy / sell
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    nav_at_purchase: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    shares: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    platform: Mapped[str] = mapped_column(String(50), default="alipay")
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    holding = relationship("Holding", back_populates="transactions")
    fund = relationship("Fund", lazy="joined")
