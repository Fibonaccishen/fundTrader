import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .database import init_db
from .routers import funds, holdings, transactions, dashboard, agent, watchlist
from .scheduler.jobs import (
    job_update_nav,
    job_update_realtime_nav,
    job_collect_market_indices,
    job_collect_sector_data,
    job_collect_news,
    job_daily_summary,
    job_cleanup,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fundtrader")

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing database...")
    await init_db()
    logger.info("Database initialized")

    # Register scheduled jobs
    # NAV update: trading days at 15:30 and 22:00 (fallback)
    scheduler.add_job(job_update_nav, "cron", hour="15,22", minute="30", id="update_nav")
    # Realtime NAV: every 5 min during trading hours (Mon-Fri 9:30-15:00)
    scheduler.add_job(job_update_realtime_nav, "cron", day_of_week="mon-fri",
                      hour="9-14", minute="*/5", id="realtime_nav")
    scheduler.add_job(job_update_realtime_nav, "cron", day_of_week="mon-fri",
                      hour="9", minute="30-59", id="realtime_nav_morning")
    # Market indices: trading days at 15:30
    scheduler.add_job(job_collect_market_indices, "cron", hour="15", minute="35",
                      day_of_week="mon-fri", id="market_indices")
    # Sector data: trading days at 16:00
    scheduler.add_job(job_collect_sector_data, "cron", hour="16", minute="0",
                      day_of_week="mon-fri", id="sector_data")
    # News: trading days at 16:00
    scheduler.add_job(job_collect_news, "cron", hour="16", minute="5",
                      day_of_week="mon-fri", id="news")
    # Daily summary: trading days at 18:00
    scheduler.add_job(job_daily_summary, "cron", hour="18", minute="0",
                      day_of_week="mon-fri", id="daily_summary")
    # Cleanup: every Sunday at 3:00
    scheduler.add_job(job_cleanup, "cron", day_of_week="sun", hour="3",
                      minute="0", id="cleanup")

    scheduler.start()
    logger.info("Scheduler started")

    yield

    # Shutdown
    scheduler.shutdown()
    logger.info("Scheduler stopped")


app = FastAPI(
    title="基金投资管家 FundTrader",
    description="Personal fund investment tracking and analysis tool",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(funds.router)
app.include_router(holdings.router)
app.include_router(transactions.router)
app.include_router(dashboard.router)
app.include_router(agent.router)
app.include_router(watchlist.router)


@app.get("/api/scheduler/status")
async def scheduler_status():
    """Get scheduler job status."""
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run_time": str(job.next_run_time) if job.next_run_time else None,
        })
    return {"running": scheduler.running, "jobs": jobs}


@app.post("/api/scheduler/trigger/{job_name}")
async def scheduler_trigger(job_name: str):
    """Manually trigger a scheduled job."""
    job_map = {
        "update_nav": job_update_nav,
        "realtime_nav": job_update_realtime_nav,
        "market_indices": job_collect_market_indices,
        "sector_data": job_collect_sector_data,
        "news": job_collect_news,
        "daily_summary": job_daily_summary,
        "cleanup": job_cleanup,
    }
    if job_name not in job_map:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Job '{job_name}' not found")

    await job_map[job_name]()
    return {"message": f"Job '{job_name}' completed"}


@app.get("/api/health")
async def health():
    return {"status": "ok"}
