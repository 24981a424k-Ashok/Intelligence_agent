import os
# Suppress TensorFlow oneDNN info logs
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2' # Also suppress general TF info/warning logs

import sys
import asyncio

# Ensure src is in path for imports
if os.getcwd() not in sys.path:
    sys.path.append(os.getcwd())

import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse
from loguru import logger
import sys

# Ensure stdout/stderr are unbuffered for Hugging Face logs
# sys.stdout.reconfigure(line_buffering=True) # For Python 3.7+
# sys.stderr.reconfigure(line_buffering=True)

from src.config import settings
from src.scheduler.task_scheduler import start_scheduler

from src.delivery.web_dashboard import router as dashboard_router
from src.delivery.user_retention import router as retention_router

# Configure logging
try:
    log_dir = os.path.join("data", "logs")
    os.makedirs(log_dir, exist_ok=True)
    logger.add(os.path.join(log_dir, "app.log"), rotation="500 MB", level="INFO")
except Exception as e:
    # If file logging fails (e.g. read-only filesystem), we fall back to stderr (default)
    # The default loguru handler is already added to stderr
    print(f"File logging disabled due to error: {e}")

from src.database.models import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting AI News Intelligence Agent...")

    # Environment Check
    required_keys = ["OPENAI_API_KEY", "NEWS_API_KEY"]
    missing_keys = [key for key in required_keys if not os.getenv(key)]
    if missing_keys:
        logger.warning(f"⚠️  MISSING CRITICAL KEYS: {', '.join(missing_keys)}. Analysis and collection may fail or use mocks.")
    
    if not os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON") and not os.path.exists("service-account.json"):
         logger.warning("⚠️  No Firebase credentials found (JSON env or file). Database/App sync might fail.")
    
    # Initialize DB
    init_db()
    logger.info("Database initialized.")

    # Initialize Firebase
    from src.config.firebase_config import initialize_firebase
    initialize_firebase()
    
    # Run one-time data fix for "0 min ago" issue and duplication
    try:
        from src.utils.fix_data import fix_data
        logger.info("Running one-time data fix (timestamps & deduplication)...")
        fix_data()
    except Exception as e:
        logger.error(f"Data fix failed: {e}")
    
    # Start Scheduler
    scheduler = start_scheduler()
    logger.info("Scheduler started.")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    if scheduler:
        scheduler.shutdown()

app = FastAPI(title="AI News Intelligence Agent", lifespan=lifespan)

# Mount static files
app.mount("/static", StaticFiles(directory="web/static"), name="static")

# Include Routers
app.include_router(retention_router, prefix="/api/retention")
app.include_router(dashboard_router)

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("web/static/favicon.png")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

def main():
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "run-once":
            logger.info("Running manual news cycle...")
            from src.scheduler.task_scheduler import run_news_cycle
            import asyncio
            asyncio.run(run_news_cycle())
        elif command == "run-twitter":
            logger.info("Running manual Twitter cycle (with Digest Update)...")
            from src.scheduler.task_scheduler import run_twitter_only_cycle
            import asyncio
            asyncio.run(run_twitter_only_cycle())
            logger.info("Manual Twitter cycle complete.")
        elif command == "init-db":
             from src.utils.init_db import init_db
             init_db()
        else:
            logger.error(f"Unknown command: {command}")
    else:
        # Run Web Server
        logger.info(f"🚀 Server starting! Access the dashboard at: http://localhost:{settings.PORT}/dashboard")
        uvicorn.run("main:app", host="0.0.0.0", port=settings.PORT, reload=False)

if __name__ == "__main__":
    main()
