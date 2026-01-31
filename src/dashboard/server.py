import os
import asyncio
from aiohttp import web
import json
from datetime import datetime
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def get_status(request):
    """
    API to get system status.
    In a real app, this would query the bot's state.
    """
    return web.json_response(
        {
            "status": "在线",
            "uptime": "0h 12m 30s",  # Mocked for now
            "strategy": "原子套利",
            "active_pairs": 2,
            "last_update": datetime.now().isoformat(),
        }
    )


async def get_logs(request):
    """
    API to get latest logs.
    Reads the tail of the log file.
    """
    log_file_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "polyarb-x.log"
    )
    logs = []

    try:
        if os.path.exists(log_file_path):
            # Read last 50 lines efficiently-ish
            with open(log_file_path, "r") as f:
                lines = f.readlines()
                logs = [line.strip() for line in lines[-50:]]
        else:
            logs = ["Log file not found at: " + log_file_path]
    except Exception as e:
        logs = [f"Error reading logs: {str(e)}"]

    return web.json_response({"logs": logs})


async def get_opportunities(request):
    """
    API to get detected opportunities.
    """
    # Mock data for demonstration
    opportunities = [
        {
            "id": 1,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "pair": "Trump vs Harris",
            "yes_price": 0.45,
            "no_price": 0.52,
            "profit": 0.03,
            "status": "已执行",
        },
        {
            "id": 2,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "pair": "FED Rate Cut",
            "yes_price": 0.12,
            "no_price": 0.89,
            "profit": -0.01,
            "status": "已忽略 (利润过低)",
        },
    ]
    return web.json_response({"opportunities": opportunities})


async def index(request):
    """Serve the index.html file."""
    return web.FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))


def init_app():
    app = web.Application()

    # Routes
    app.router.add_get("/", index)
    app.router.add_get("/api/status", get_status)
    app.router.add_get("/api/logs", get_logs)
    app.router.add_get("/api/opportunities", get_opportunities)

    # Static files
    static_path = os.path.join(os.path.dirname(__file__), "static")
    if not os.path.exists(static_path):
        os.makedirs(static_path)
    app.router.add_static("/static/", static_path)

    return app


if __name__ == "__main__":
    app = init_app()
    web.run_app(app, port=8080)
