import os
# Suppress TensorFlow oneDNN info logs
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2' # Also suppress general TF info/warning logs

import sys
import asyncio
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse
from loguru import logger

from src.config import settings
from src.scheduler.task_scheduler import start_scheduler
# from src.delivery.web_dashboard import app as dashboard_app # Circular import if we are not careful

from src.delivery.web_dashboard import router as dashboard_router
from src.delivery.user_retention import router as retention_router

# Configure logging
logger.add("logs/app.log", rotation="500 MB", level="INFO")

from src.database.models import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting AI News Intelligence Agent...")
    
    # Initialize DB
    init_db()
    logger.info("Database initialized.")

    # Initialize Firebase
    from src.config.firebase_config import initialize_firebase
    initialize_firebase()
    
    # Start Scheduler
    scheduler = start_scheduler()
    logger.info("Scheduler started.")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    if scheduler:
        scheduler.shutdown()

app = FastAPI(title="AI News Intelligence Agent", lifespan=lifespan)

# Firebase Functions Export - Disabled as it conflicts with generic ASGI/Docker deployment
# try:
#     from firebase_functions import https_fn
#     api = https_fn.on_request(app)
# except ImportError:
#     pass

# Mount static files
app.mount("/static", StaticFiles(directory="web/static"), name="static")

# Include Routers
app.include_router(retention_router, prefix="/api/retention")
app.include_router(dashboard_router)

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("web/static/favicon.png")

@app.api_route("/api/{path_name:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def debug_api_requests(path_name: str, request: Request):
    logger.warning(f"Unmatched API Request: {request.method} /api/{path_name}")
    return Response(content='{"detail": "Not Found"}', status_code=404, media_type="application/json")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

def main():
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "run-once":
            logger.info("Running manual news cycle...")
            from src.scheduler.task_scheduler import run_news_cycle
            run_news_cycle()
        elif command == "init-db":
             from src.utils.init_db import init_db
             init_db()
        else:
            logger.error(f"Unknown command: {command}")
    else:
        # Run Web Server
        uvicorn.run("main:app", host="0.0.0.0", port=settings.PORT, reload=True)

if __name__ == "__main__":
    main()
