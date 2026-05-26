import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

DATABASE_URL = f"sqlite+aiosqlite:///{DATA_DIR / 'fundtrader.db'}"

# External API settings
EASTMONEY_FUND_LIST_URL = "http://fund.eastmoney.com/js/fundcode_search.js"
EASTMONEY_FUND_DETAIL_URL = "http://fund.eastmoney.com/pingzhongdata/{code}.js"
EASTMONEY_NAV_HISTORY_URL = "https://api.fund.eastmoney.com/f10/lsjz"
TIANTIAN_REALTIME_URL = "https://fundgz.1234567.com.cn/js/{code}.js"

HTTP_TIMEOUT = 15
HTTP_MAX_CONCURRENT = 3

# Trading hours (Beijing time)
TRADING_START_HOUR = 9
TRADING_START_MIN = 30
TRADING_END_HOUR = 15
TRADING_END_MIN = 0
