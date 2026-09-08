"""Run with: python run.py"""
import sys
import asyncio
import uvicorn
from src.config import settings

# Prevent Windows ProactorEventLoop from starving I/O during heavy CPU inference
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

if __name__ == "__main__":
    uvicorn.run(
        "src.server:app",
        host=settings.HOST,
        port=settings.PORT,
        log_level=settings.LOG_LEVEL.lower(),
        # Passing None disables Uvicorn's ping/pong timeout disconnects locally
        ws_ping_interval=None,
        ws_ping_timeout=None,
    )