import json
import os
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.holding import Holding
from ..models.fund import Fund
from ..models.transaction import Transaction
from ..models.nav_snapshot import NavSnapshot
from ..models.market_data import DailySummary, MarketIndex, SectorData, FinancialNews
from ..schemas.schemas import (
    AgentPortfolioItem, AgentDailySummary, AgentNotesCreate,
    MarketIndexOut, SectorOut, NewsOut,
)
from ..services.portfolio import get_latest_nav_for_fund, calc_holding_pnl
from ..services.fund_data import fetch_realtime_estimation

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.get("/portfolio", response_model=list[AgentPortfolioItem])
async def agent_portfolio(db: AsyncSession = Depends(get_db)):
    """Full portfolio snapshot for AI agent consumption."""
    result = await db.execute(select(Holding).where(Holding.status == "active"))
    holdings = result.scalars().all()

    output = []
    for h in holdings:
        unit_nav, est_nav, daily_change = await get_latest_nav_for_fund(db, h.fund_id)
        est = await fetch_realtime_estimation(h.fund.code)
        if est:
            if est.get("gszzl") and not daily_change:
                daily_change = Decimal(str(est["gszzl"]))
            if not unit_nav and est.get("gsz"):
                est_nav = Decimal(str(est["gsz"]))

        current_nav = unit_nav or est_nav
        pnl = calc_holding_pnl(h, current_nav)
        avg_cost = None
        if h.total_shares > 0:
            avg_cost = (h.total_cost / h.total_shares).quantize(Decimal("0.0001"))

        output.append(AgentPortfolioItem(
            fund_code=h.fund.code,
            fund_name=h.fund.name,
            fund_type=h.fund.fund_type,
            total_shares=h.total_shares,
            total_cost=h.total_cost,
            avg_cost_per_share=avg_cost,
            current_nav=current_nav,
            market_value=pnl["market_value"],
            unrealized_pnl=pnl["unrealized_pnl"],
            pnl_pct=pnl["pnl_pct"],
            daily_change_pct=daily_change,
            strategy_type=h.strategy_type,
            status=h.status,
        ))
    return output


@router.get("/fund/{code}/full-detail")
async def agent_fund_detail(code: str, db: AsyncSession = Depends(get_db)):
    """Full fund detail: info, all transactions, NAV history."""
    result = await db.execute(select(Fund).where(Fund.code == code))
    fund = result.scalar_one_or_none()
    if not fund:
        raise HTTPException(status_code=404, detail="Fund not found")

    # Holding
    holding_result = await db.execute(
        select(Holding).where(Holding.fund_id == fund.id)
    )
    holding = holding_result.scalar_one_or_none()

    # Transactions
    txn_result = await db.execute(
        select(Transaction).where(Transaction.fund_id == fund.id)
        .order_by(Transaction.transaction_date.desc())
    )
    transactions = txn_result.scalars().all()

    # NAV history
    nav_result = await db.execute(
        select(NavSnapshot).where(NavSnapshot.fund_id == fund.id)
        .order_by(NavSnapshot.nav_date.desc()).limit(365)
    )
    navs = nav_result.scalars().all()

    # P&L
    pnl_info = {}
    if holding:
        unit_nav, _, _ = await get_latest_nav_for_fund(db, holding.fund_id)
        pnl_info = calc_holding_pnl(holding, unit_nav)

    return {
        "fund": {"code": fund.code, "name": fund.name, "type": fund.fund_type, "company": fund.company},
        "holding": {
            "total_shares": str(holding.total_shares) if holding else "0",
            "total_cost": str(holding.total_cost) if holding else "0",
            "strategy_type": holding.strategy_type if holding else None,
            "status": holding.status if holding else None,
        } if holding else None,
        "pnl": {k: str(v) for k, v in pnl_info.items()} if pnl_info else None,
        "transactions": [
            {
                "type": t.transaction_type, "date": str(t.transaction_date),
                "amount": str(t.amount), "nav": str(t.nav_at_purchase),
                "shares": str(t.shares), "fee": str(t.fee),
            }
            for t in transactions
        ],
        "nav_history": [
            {
                "date": str(n.nav_date), "unit_nav": str(n.unit_nav) if n.unit_nav else None,
                "accumulated_nav": str(n.accumulated_nav) if n.accumulated_nav else None,
                "change_pct": str(n.daily_change_pct) if n.daily_change_pct else None,
            }
            for n in reversed(navs)
        ],
    }


@router.get("/market/today")
async def agent_market_today(db: AsyncSession = Depends(get_db)):
    """Today's market summary for agent consumption."""
    today = date.today()

    # Latest indices
    idx_result = await db.execute(
        select(MarketIndex).where(MarketIndex.record_date == today)
        .order_by(MarketIndex.index_code)
    )
    indices = idx_result.scalars().all()
    if not indices:
        idx_result = await db.execute(
            select(MarketIndex).order_by(MarketIndex.record_date.desc()).limit(4)
        )
        indices = idx_result.scalars().all()

    # Latest sectors
    sec_result = await db.execute(
        select(SectorData).order_by(SectorData.record_date.desc()).limit(20)
    )
    sectors = sec_result.scalars().all()

    # Latest news
    news_result = await db.execute(
        select(FinancialNews).where(FinancialNews.collected_at >= today - timedelta(days=3))
        .order_by(FinancialNews.collected_at.desc()).limit(20)
    )
    news = news_result.scalars().all()

    return {
        "indices": [
            {"name": m.index_name, "close": str(m.close_price) if m.close_price else None,
             "change_pct": str(m.change_pct) if m.change_pct else None}
            for m in indices
        ],
        "sectors": [
            {"name": s.sector_name, "change_pct": str(s.change_pct) if s.change_pct else None}
            for s in sectors
        ],
        "news": [
            {"title": n.title, "source": n.source, "summary": n.summary,
             "tags": n.relevance_tags}
            for n in news
        ],
    }


@router.get("/market/sectors", response_model=list[SectorOut])
async def agent_sectors(query_date: date | None = None, db: AsyncSession = Depends(get_db)):
    """Sector performance for a specific date."""
    if query_date is None:
        query_date = date.today()
    result = await db.execute(
        select(SectorData).where(SectorData.record_date == query_date)
        .order_by(SectorData.change_pct.desc())
    )
    sectors = result.scalars().all()
    return [
        SectorOut(sector_name=s.sector_name, sector_code=s.sector_code,
                  record_date=s.record_date, change_pct=s.change_pct)
        for s in sectors
    ]


@router.get("/news", response_model=list[NewsOut])
async def agent_news(
    days: int = 7,
    tags: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Recent financial news, optionally filtered by tags."""
    since = date.today() - timedelta(days=days)
    query = select(FinancialNews).where(
        FinancialNews.collected_at >= since
    ).order_by(FinancialNews.collected_at.desc()).limit(50)
    result = await db.execute(query)
    news_list = result.scalars().all()

    output = []
    tag_list = [t.strip() for t in tags.split(",")] if tags else []
    for n in news_list:
        if tag_list and n.relevance_tags:
            try:
                import json
                ntags = json.loads(n.relevance_tags)
                if not any(t in ntags for t in tag_list):
                    continue
            except Exception:
                pass
        output.append(NewsOut(
            title=n.title, source=n.source, url=n.url, summary=n.summary,
            publish_time=n.publish_time, relevance_tags=n.relevance_tags,
        ))
    return output


@router.get("/daily-summary/{summary_date}")
async def agent_daily_summary(summary_date: str, db: AsyncSession = Depends(get_db)):
    """Get daily summary for a specific date."""
    dt = date.fromisoformat(summary_date)
    result = await db.execute(
        select(DailySummary).where(DailySummary.summary_date == dt)
    )
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Summary not found for this date")
    return AgentDailySummary(
        summary_date=s.summary_date,
        total_market_value=s.total_market_value,
        total_cost=s.total_cost,
        total_pnl=s.total_pnl,
        pnl_pct=s.pnl_pct,
        market_sentiment=s.market_sentiment,
        ai_notes=s.ai_notes,
    )


@router.post("/summaries", status_code=201)
async def agent_write_summary(data: AgentNotesCreate, db: AsyncSession = Depends(get_db)):
    """Agent writes notes/insights to a daily summary."""
    result = await db.execute(
        select(DailySummary).where(DailySummary.summary_date == data.summary_date)
    )
    s = result.scalar_one_or_none()
    if not s:
        s = DailySummary(summary_date=data.summary_date)
        db.add(s)
    if data.market_sentiment is not None:
        s.market_sentiment = data.market_sentiment
    if data.ai_notes is not None:
        s.ai_notes = data.ai_notes
    await db.flush()
    return {"message": "Summary updated"}


@router.get("/manual")
async def agent_manual():
    """Return the operations manual for the AI agent."""
    manual_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "..", "docs", "AGENT_MANUAL.md"
    )
    manual_path = os.path.abspath(manual_path)
    if not os.path.exists(manual_path):
        raise HTTPException(status_code=404, detail="Manual not found")
    with open(manual_path, "r", encoding="utf-8") as f:
        content = f.read()
    return {"content": content}


# ---- User Settings ----
from ..models.user_settings import UserSettings as UserSettingsModel
from pydantic import BaseModel as PydanticBase


async def _calc_remaining_cash(db: AsyncSession, total_capital: Decimal) -> float:
    """Auto-calculate remaining cash: total_capital - sum of all holding costs."""
    result = await db.execute(
        select(Holding).where(Holding.status == "active")
    )
    holdings = result.scalars().all()
    total_invested = sum((h.total_cost for h in holdings), Decimal("0"))
    remaining = float(total_capital - total_invested)
    return remaining


class UserSettingsIn(PydanticBase):
    total_capital: float | None = None
    monthly_contribution: float | None = None
    stop_profit_pct: float | None = None
    stop_loss_pct: float | None = None
    investment_goal: str | None = None
    risk_tolerance: str | None = None
    personal_opinion: str | None = None
    notes: str | None = None


@router.get("/settings")
async def get_settings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserSettingsModel).limit(1))
    s = result.scalar_one_or_none()
    total_capital = s.total_capital if s else Decimal("0")
    remaining = await _calc_remaining_cash(db, total_capital)
    if not s:
        return {
            "total_capital": 0, "remaining_cash": 0,
            "monthly_contribution": None, "stop_profit_pct": None, "stop_loss_pct": None,
            "investment_goal": None, "risk_tolerance": "medium",
            "personal_opinion": None, "notes": None,
        }
    return {
        "total_capital": float(total_capital),
        "remaining_cash": remaining,
        "monthly_contribution": float(s.monthly_contribution) if s.monthly_contribution else None,
        "stop_profit_pct": float(s.stop_profit_pct) if s.stop_profit_pct else None,
        "stop_loss_pct": float(s.stop_loss_pct) if s.stop_loss_pct else None,
        "investment_goal": s.investment_goal,
        "risk_tolerance": s.risk_tolerance,
        "personal_opinion": s.personal_opinion,
        "notes": s.notes,
    }


@router.put("/settings")
async def update_settings(data: UserSettingsIn, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserSettingsModel).limit(1))
    s = result.scalar_one_or_none()
    if not s:
        s = UserSettingsModel()
        db.add(s)
    if data.total_capital is not None:
        s.total_capital = Decimal(str(data.total_capital))
    if data.monthly_contribution is not None:
        s.monthly_contribution = Decimal(str(data.monthly_contribution))
    if data.stop_profit_pct is not None:
        s.stop_profit_pct = Decimal(str(data.stop_profit_pct))
    if data.stop_loss_pct is not None:
        s.stop_loss_pct = Decimal(str(data.stop_loss_pct))
    if data.investment_goal is not None:
        s.investment_goal = data.investment_goal
    if data.risk_tolerance is not None:
        s.risk_tolerance = data.risk_tolerance
    if data.personal_opinion is not None:
        s.personal_opinion = data.personal_opinion
    if data.notes is not None:
        s.notes = data.notes
    await db.flush()
    total_capital = s.total_capital if s.total_capital else Decimal("0")
    remaining = await _calc_remaining_cash(db, total_capital)
    return {"message": "Settings updated", "remaining_cash": remaining}


# ---- Daily Analysis ----
@router.get("/analysis")
async def daily_analysis(db: AsyncSession = Depends(get_db)):
    """Generate a comprehensive daily analysis with recommendations."""
    today = date.today()

    # 1. User settings
    settings_result = await db.execute(select(UserSettingsModel).limit(1))
    settings = settings_result.scalar_one_or_none()
    total_capital = settings.total_capital if settings else Decimal("0")
    remaining_cash = Decimal(str(await _calc_remaining_cash(db, total_capital)))

    # 2. Portfolio
    holdings_result = await db.execute(select(Holding).where(Holding.status == "active"))
    holdings = holdings_result.scalars().all()

    portfolio_data = []
    total_market = Decimal("0")
    total_cost = Decimal("0")
    for h in holdings:
        unit_nav, est_nav, _ = await get_latest_nav_for_fund(db, h.fund_id)
        nav = unit_nav or est_nav
        if nav:
            mv = h.total_shares * nav
        else:
            mv = Decimal("0")
        pnl = mv - h.total_cost
        pnl_pct = (pnl / h.total_cost * 100).quantize(Decimal("0.01")) if h.total_cost > 0 else Decimal("0")
        total_market += mv
        total_cost += h.total_cost
        portfolio_data.append({
            "fund_code": h.fund.code, "fund_name": h.fund.name,
            "fund_type": h.fund.fund_type, "strategy_type": h.strategy_type,
            "total_cost": float(h.total_cost), "market_value": float(mv),
            "unrealized_pnl": float(pnl), "pnl_pct": float(pnl_pct),
            "current_nav": float(nav) if nav else None,
        })

    invested = total_cost
    total_pnl = total_market - total_cost
    total_pnl_pct = float(total_pnl / total_cost * 100) if total_cost > 0 else 0

    # 3. Market indices
    idx_result = await db.execute(
        select(MarketIndex).order_by(MarketIndex.record_date.desc()).limit(4)
    )
    indices = idx_result.scalars().all()

    # 4. Sector data
    sec_result = await db.execute(
        select(SectorData).order_by(SectorData.record_date.desc()).limit(7)
    )
    sectors = sec_result.scalars().all()

    # 5. Recent news
    news_result = await db.execute(
        select(FinancialNews).order_by(FinancialNews.collected_at.desc()).limit(15)
    )
    news = news_result.scalars().all()

    # 6. Risk & custom thresholds
    risk = (settings.risk_tolerance if settings and settings.risk_tolerance else "medium")
    risk_map = {"low": "保守型", "medium": "稳健型", "high": "激进型"}
    risk_label = risk_map.get(risk, "稳健型")

    stop_profit = settings.stop_profit_pct if settings and settings.stop_profit_pct else None
    stop_loss = settings.stop_loss_pct if settings and settings.stop_loss_pct else None
    sp = float(stop_profit) if stop_profit else None
    sl = float(stop_loss) if stop_loss else None

    # Default thresholds by risk level
    default_sp = {"low": 8, "medium": 10, "high": 15}.get(risk, 10)
    default_sl = {"low": -5, "medium": -8, "high": -15}.get(risk, -8)

    sp_val = sp if sp is not None else default_sp
    sl_val = sl if sl is not None else default_sl

    personal = settings.personal_opinion if settings and settings.personal_opinion else None

    # Build news with summaries for prompt
    news_lines = []
    for n in news[:10]:
        tags_str = ", ".join(json.loads(n.relevance_tags)) if n.relevance_tags else ""
        tag_prefix = f" [{tags_str}]" if tags_str else ""
        summary = n.summary if n.summary else ""
        news_lines.append(f"-{tag_prefix} {n.title}" + (f"：{summary[:80]}" if summary else ""))

    # --- BUILD ANALYSIS PROMPT ---
    sp_note = " (自定义)" if sp else " (默认)"
    sl_note = " (自定义)" if sl else " (默认)"
    personal_section = ""
    if personal:
        personal_section = "### 用户个人意见\n" + personal + "\n"

    prompt = f"""## 基金投资每日分析任务

你是一位专业的基金投资顾问。请根据以下数据，给出**明确、具体、可执行**的投资建议。

### 用户资金状况
- 总本金: {float(total_capital):.0f} 元
- 已投入: {float(invested):.0f} 元 ({round(float(invested/total_capital*100) if total_capital > 0 else 0, 1)}%)
- 剩余可用资金: {float(remaining_cash):.0f} 元
- 当前总市值: {float(total_market):.0f} 元
- 总盈亏: {float(total_pnl):.0f} 元 ({round(total_pnl_pct, 2)}%)

### 用户风险偏好
**类型：{risk_label}**
- 止盈线：**+{sp_val}%**{sp_note}
- 止损线：**{sl_val}%**{sl_note}
{personal_section}
### 当前持仓
"""
    for p in portfolio_data:
        strat = "【长线定投】" if p['strategy_type'] == 'long_term' else "【短线操作】"
        prompt += f"- {strat} {p['fund_name']}({p['fund_code']}) | {p['fund_type']} | 成本{p['total_cost']:.0f}元 | 市值{p['market_value']:.0f}元 | 盈亏{p['unrealized_pnl']:.0f}元({p['pnl_pct']}%)\n"

    prompt += f"""
### 今日大盘
"""
    for m in indices:
        prompt += f"- {m.index_name}: {m.close_price:.2f} ({m.change_pct:+.2f}%)\n"

    prompt += f"""
### 热门板块表现
"""
    for s in sectors:
        prompt += f"- {s.sector_name}: {s.change_pct:+.2f}%\n" if s.change_pct else f"- {s.sector_name}\n"

    prompt += f"""
### 系统采集的近期新闻（标题摘要，需进一步验证）
"""
    for nl in news_lines:
        prompt += nl + "\n"

    prompt += f"""
### 新闻查询渠道（请务必访问以下网站获取最新信息后综合分析）
1. **天天基金/东方财富** (fund.eastmoney.com / eastmoney.com) — 基金净值、排名、公告、研报
2. **巨潮资讯** (cninfo.com.cn) — 上市公司公告、财报
3. **雪球** (xueqiu.com) — 投资者社区讨论、市场情绪
4. **财联社** (cls.cn) — 7x24小时快讯、电报
5. **新浪财经** (finance.sina.com.cn) — 宏观经济政策、央行动态
6. **东方财富股吧** (guba.eastmoney.com) — 基金吧、股票吧讨论
7. **同花顺** (10jqka.com.cn) — 板块资金流向、个股分析

### 分析方法指导
1. 先查询各持仓基金对应板块的近期新闻、政策、资金流向
2. 根据板块强弱和基金表现，判断是否调整仓位
3. 长线定投型基金：关注基本面变化，一般不轻易止损，大跌时可适当加仓
4. 短线操作型基金：关注技术面和资金流向，达到止盈目标应果断减仓

### 风控规则（基于用户设置）
- 止盈线: +{sp_val}% (盈利超过此线应分批止盈，短线可更积极)
- 止损线: {sl_val}% (亏损超过此线应果断减仓，长线可适度放宽)
- 短线操作参考止盈+{min(sp_val, 10)}%，长线可放宽至+{min(sp_val + 10, 30)}%
- 单只基金仓位上限: 总仓位的40% (即{(float(total_capital) * 0.4):.0f}元)

### 关于用户设置的说明
- 用户的止盈止损线、个人意见仅作为参考，你是经验丰富的基金经理
- 如果你判断用户的设置不合理（如止盈线过高、止损线过松），应明确指出并给出更专业的建议
- 如果用户个人意见与市场实际情况不符，不必盲从，用数据说服用户
- 最终目标是在用户风险偏好框架内，做出最优的投资决策

### ⚠️ 必须输出的建议格式（必须具体到金额！）

**现有持仓调整建议：**
- {p['fund_name']}({p['fund_code']}): [加仓/减仓/持有] [具体金额 元]，理由：[分析理由]
- [对每只持仓都给出明确建议]

**新基金推荐（如有）：**
- 推荐方向：[具体板块/主题]
- 建议投入：[具体金额 元]
- 推荐理由：[市场分析、政策利好等]

**风险提示：**
- [当前市场主要风险]
- [需要注意的持仓风险]

**执行优先级：**
1. [最优先的操作]
2. [次优先的操作]

👆 注意：你的建议要能直接执行，金额必须精确到元。所有建议基于用户{risk_label}风险偏好（止盈+{sp_val}%/止损{sl_val}%）。"""

    # Build analysis response
    return {
        "analysis_date": str(today),
        "risk_tolerance": risk,
        "risk_description": f"{risk_label}（止盈+{sp_val}%/止损{sl_val}%）",
        "stop_profit_pct": sp_val,
        "stop_loss_pct": sl_val,
        "personal_opinion": personal,
        "user_financials": {
            "total_capital": float(total_capital),
            "invested": float(invested),
            "remaining_cash": float(remaining_cash),
            "total_market_value": float(total_market),
            "total_pnl": float(total_pnl),
            "total_pnl_pct": round(total_pnl_pct, 2),
            "positions_used_pct": round(float(invested / total_capital * 100), 1) if total_capital > 0 else 0,
        },
        "portfolio": portfolio_data,
        "market_indices": [
            {"name": m.index_name, "close": float(m.close_price) if m.close_price else None,
             "change_pct": float(m.change_pct) if m.change_pct else None}
            for m in indices
        ],
        "hot_sectors": [
            {"name": s.sector_name, "change_pct": float(s.change_pct) if s.change_pct else None}
            for s in sectors
        ],
        "recent_news": [
            {"title": n.title, "source": n.source or "", "tags": n.relevance_tags,
             "summary": n.summary or "", "url": n.url or ""}
            for n in news
        ],
        "analysis_prompt": prompt,
    }

