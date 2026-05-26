# 📈 FundTrader — Your AI Investment Co-pilot

> Track every trade. Understand every cent. Let AI analyze and advise — **you make the final call.**

*[中文文档](README_CN.md)*

---

## What is this?

You bought some mutual funds on Alipay. Every day you check the red and green numbers, but you're not sure: Am I actually making money? Should I add more? Time to cut losses?

**FundTrader** is a locally-run fund investment management tool. It connects to public Chinese fund market data and helps you do three things:

1. **Track & Monitor** — Record every trade, auto-fetch NAVs, calculate real-time P&L
2. **Data Collection** — Auto-collect market indices, sector performance, financial news daily
3. **AI Analysis** — Generate structured analysis prompts combining your portfolio, market data, news, and risk preferences. Feed them to any AI Agent for **dollar-precise** trading advice.

> 💡 **What makes FundTrader different**: It's not just a data dashboard. It's designed as a **data infrastructure for AI Agents** — complete with REST APIs, scheduled data collection, and an Agent operations manual. Give an AI agent the big picture every morning, and it'll tell you exactly what to buy, sell, or hold.

---

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- Node.js 18+
- Internet access to Chinese fund data APIs (works from mainland China)

### One-Command Setup (via AI Agent)

Copy this to [Claude Code](https://claude.ai/code) or your AI agent:

```
Help me install and start this project: https://github.com/Fibonaccishen/fundTrader

Steps:
1. cd to the project directory
2. cd backend && pip install -r requirements.txt
3. cd ../frontend && npm install
4. Start backend: cd backend && uvicorn app.main:app --port 8000 --reload
5. Start frontend: cd frontend && npm run dev
6. Open http://localhost:5173 and confirm it works

If any step fails, diagnose and fix it — don't just tell me the error.
```

### Manual Setup

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** in your browser.
API docs: **http://localhost:8000/docs**

---

## 🌟 Features

### 📊 Dashboard

One screen, everything you need: total market value, cumulative P&L, today's P&L, available cash. Market value trend chart, strategy allocation pie chart, fund allocation pie chart.

### 💰 Portfolio Management

Each fund has a card: current NAV, market value, P&L, daily change %. Click into a fund detail page — **180-day NAV trend chart** with buy/sell markers (red pins for buys, green for sells). Every transaction is editable and deletable.

**Quick buy/sell** directly from the card — no page switching needed.

### 🤖 AI Daily Analysis (Core Feature)

Click "**Refresh + Analyze**" and the system automatically:
1. Pulls the latest NAVs for all holdings
2. Collects today's market indices and sector performance
3. Fetches the latest financial news with summaries
4. Reads your risk tolerance, stop-profit/stop-loss thresholds, and personal notes
5. **Generates a 2,500+ character structured analysis prompt**

The prompt includes:
- Complete financial snapshot (total capital / invested / available / P&L)
- Per-holding cost / market value / P&L breakdown
- Real-time data for 4 major indices
- Hot sector performance
- Recent news headlines with summaries
- **7 news research sources** (tells AI where to find the latest info)
- Risk management rules (custom stop-profit +12% / stop-loss -7%)
- Your personal investment opinions
- **Requires AI to give yuan-precise trade recommendations**
- Explicitly tells AI: "You are an experienced fund manager — override user if needed"

**One-click copy** the prompt → paste to ChatGPT / Claude → get specific advice.

### 🔍 Watchlist

Funds you're considering but haven't bought yet. Add them to your watchlist. Each shows a 30-day mini trend chart. One click to jump to the buy page.

### ⚠️ Risk Analysis

Automatic sector concentration detection. 97% of your portfolio in semiconductors/chips? The system flags it in red: "Over-concentrated! Consider diversifying."

### 📉 Market Valuation

PE percentile data for CSI 300 / CSI 500 / ChiNext. Green = undervalued, yellow = fair, red = overvalued. Know whether the market is cheap or expensive at a glance.

### 📰 Market Data

Real-time quotes for 4 major indices + 7 hot sector performances + 15 financial news headlines.

### ⏰ Automated Scheduling

Runs 24/7 in the background:
- NAV updates at 15:30 on trading days
- Real-time NAV estimates every 5 minutes during market hours
- Index, sector, and news collection after market close
- Daily portfolio summary at 18:00
- Weekly data cleanup on Sundays

---

## 🏗️ Feature Overview

| Module | Capabilities |
|--------|-------------|
| **Dashboard** | P&L cards, trend chart, strategy & fund pie charts, available cash |
| **Portfolio** | Buy/sell/edit/delete trades, real-time P&L, quick add/reduce position dialogs |
| **Fund Detail** | 180-day NAV trend (with trade markers), full transaction history |
| **AI Daily Analysis** | One-click structured prompt generation: portfolio + market + news + risk rules |
| **Watchlist** | Track candidate funds, 30-day mini charts, one-click buy |
| **Risk Analysis** | Sector concentration detection, multi-level warnings |
| **Market Valuation** | CSI 300 / CSI 500 / ChiNext PE percentiles, under/overvalued labels |
| **Market Data** | 4 indices + 7 sectors + financial news |
| **Capital Management** | Total capital - position costs = available cash, auto-calculated |
| **Agent API** | `/api/agent/*` endpoints + complete operations manual |
| **Scheduled Tasks** | NAV / index / sector / news auto-collection daily |

---

## 📂 Project Structure

```
fundTrader/
├── backend/app/
│   ├── main.py              # FastAPI entry + 8 scheduled jobs
│   ├── models/              # 10 database tables
│   ├── routers/             # 6 route modules
│   ├── services/            # Fund data fetching / P&L calculation
│   ├── scheduler/           # APScheduler job definitions
│   └── utils/               # JS/JSONP response parser
├── frontend/src/
│   ├── views/               # 6 pages
│   ├── components/          # Nav + Holding card
│   ├── router/ api/ stores/ # Vue Router / Axios / Pinia
├── docs/AGENT_MANUAL.md     # AI Agent operations manual (Chinese)
└── data/                    # SQLite database (local only)
```

## 🛠️ Tech Stack

| Layer | Choice |
|-------|--------|
| Backend | Python + FastAPI + SQLAlchemy 2.0 (async) |
| Database | SQLite (zero-config, file-based) |
| Scheduler | APScheduler (embedded, no Redis needed) |
| Frontend | Vue 3 + Vite + Element Plus + ECharts |
| Data Sources | TianTian Fund / EastMoney / Sina Finance |

---

## 🔌 Data Sources

| Data | Source |
|------|--------|
| Real-time fund NAV estimates | `fundgz.1234567.com.cn` (TianTian Fund) |
| Fund master data & list | `fund.eastmoney.com` (EastMoney) |
| Historical NAV trends | `fund.eastmoney.com/pingzhongdata` |
| Market index quotes | `push2.eastmoney.com` |
| Financial news | `feed.mix.sina.com.cn` (Sina Finance) |

> All data is stored locally in `data/fundtrader.db`. No personal information is ever uploaded.

---

## 🤖 AI Agent Integration

This is the core differentiator of FundTrader. You don't need to analyze data manually — let AI do it:

1. The system auto-collects all data daily
2. Open Dashboard, click "Refresh + Analyze" (or "Quick Analyze")
3. Copy the generated prompt, send to Claude / ChatGPT / any LLM
4. AI gives you **yuan-precise buy/sell/hold recommendations** based on your actual holdings, market conditions, news, and risk preferences

For detailed workflow, see **[AGENT_MANUAL.md](docs/AGENT_MANUAL.md)** (in Chinese).

---

## 📋 Roadmap

### Done

- [x] Portfolio management (buy/sell/edit/delete)
- [x] Auto NAV fetching & real-time P&L calculation
- [x] NAV trend chart with buy/sell markers
- [x] Dashboard (summary cards + trend chart + pie charts)
- [x] AI daily analysis (structured prompt generation)
- [x] Unified capital management (auto-calculated available cash)
- [x] Custom stop-profit/stop-loss + risk tolerance + personal notes
- [x] Risk analysis (sector concentration)
- [x] Watchlist (mini trend charts + one-click buy)
- [x] Market valuation (PE percentiles)
- [x] Market data (indices + sectors + news)
- [x] Scheduled automation
- [x] Agent API + operations manual

### Planned

- [ ] Portfolio drilling (overlapping underlying stock analysis)
- [ ] Paper trading / strategy backtesting (DCA verification)
- [ ] Smart fund picker (multi-dimensional scoring)
- [ ] WeChat Mini Program
- [ ] Native AI Agent auto-invocation (not just prompt generation)

---

## ⚖️ Design Principles

- **Tool assists, user decides**: Analysis and advice are provided, but you make every trade decision
- **Data transparency**: Every calculation is visible and verifiable
- **No backend AI**: No LLM APIs are called without your knowledge. AI features work by generating prompts you send yourself
- **Local first**: All data in local SQLite. No account registration. No data upload. No tracking.

---

## 📄 License

MIT

---

*Made with ❤️ by a retail investor, for retail investors.*
