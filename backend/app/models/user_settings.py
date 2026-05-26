from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, DateTime, Numeric, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base


class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    total_capital: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)  # 总本金
    monthly_contribution: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))  # 每月计划定投金额
    stop_profit_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))  # 止盈线 %
    stop_loss_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))  # 止损线 %
    investment_goal: Mapped[str | None] = mapped_column(Text)  # 投资目标
    risk_tolerance: Mapped[str | None] = mapped_column(String(20))  # low/medium/high/custom
    personal_opinion: Mapped[str | None] = mapped_column(Text)  # 个人意见/想法
    notes: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
