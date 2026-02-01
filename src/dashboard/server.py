"""
PolyArb-X Dashboard Server

FastAPI server for real-time monitoring dashboard.
"""
import os
import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from aiohttp import web


# Get project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
LOG_FILE = PROJECT_ROOT / "data" / "polyarb-x.log"
MARKETS_FILE = PROJECT_ROOT / "data" / "active_markets.json"
EVENTS_DIR = PROJECT_ROOT / "data" / "events"


def parse_log_uptime() -> str:
    """Parse uptime from log file."""
    try:
        if not LOG_FILE.exists():
            return "0h 0m 0s"

        # Get first and last log entries
        with open(LOG_FILE, 'r') as f:
            lines = f.readlines()

        if len(lines) < 2:
            return "0h 0m 0s"

        # Extract timestamps
        first_line = lines[0]
        last_line = lines[-1]

        # Parse datetime
        time_format = "%Y-%m-%d %H:%M:%S"
        first_time = datetime.strptime(first_line.split("|")[0].strip(), time_format)
        last_time = datetime.strptime(last_line.split("|")[0].strip(), time_format)

        # Calculate uptime
        delta = last_time - first_time
        hours = int(delta.total_seconds() // 3600)
        minutes = int((delta.total_seconds() % 3600) // 60)
        seconds = int(delta.total_seconds() % 60)

        return f"{hours}h {minutes}m {seconds}s"

    except Exception:
        return "0h 0m 0s"


def parse_log_stats() -> Dict:
    """Parse statistics from log file."""
    stats = {
        "opportunities": 0,
        "trades": 0,
        "checks": 0,
        "messages": 0,
    }

    try:
        if not LOG_FILE.exists():
            return stats

        with open(LOG_FILE, 'r') as f:
            lines = f.readlines()

        for line in lines:
            if "检测到套利机会" in line or "🎯" in line:
                stats["opportunities"] += 1
            if "执行交易" in line or "[模拟模式]" in line:
                stats["trades"] += 1
            if "检查次数" in line:
                match = re.search(r'检查次数:\s*(\d+)', line)
                if match:
                    stats["checks"] = int(match.group(1))

        # Get message count from WebSocket logs
        for line in lines[-100:]:  # Check recent lines
            if "收到" in line and "消息" in line:
                match = re.search(r'收到\s*(\d+)', line)
                if match:
                    stats["messages"] = int(match.group(1))

    except Exception as e:
        print(f"Error parsing stats: {e}")

    return stats


def get_market_info() -> Dict:
    """Get market information from active_markets.json."""
    try:
        if not MARKETS_FILE.exists():
            return {
                "total_markets": 0,
                "total_tokens": 0,
                "total_volume": 0,
                "total_liquidity": 0,
            }

        with open(MARKETS_FILE, 'r') as f:
            markets = json.load(f)

        total_volume = sum(m.get('volume_24h', 0) for m in markets)
        total_liquidity = sum(m.get('liquidity', 0) for m in markets)

        return {
            "total_markets": len(markets),
            "total_tokens": len(markets) * 2,  # YES + NO for each market
            "total_volume": total_volume,
            "total_liquidity": total_liquidity,
            "avg_volume": total_volume / len(markets) if markets else 0,
            "avg_liquidity": total_liquidity / len(markets) if markets else 0,
        }

    except Exception as e:
        print(f"Error reading markets: {e}")
        return {
            "total_markets": 0,
            "total_tokens": 0,
            "total_volume": 0,
            "total_liquidity": 0,
        }


async def get_status(request):
    """API to get system status."""
    stats = parse_log_stats()
    markets = get_market_info()
    uptime = parse_log_uptime()

    return web.json_response(
        {
            "status": "在线",
            "mode": "dry-run",
            "uptime": uptime,
            "strategy": "原子套利",
            "subscribed_markets": markets["total_markets"],
            "subscribed_tokens": markets["total_tokens"],
            "total_volume": markets["total_volume"],
            "total_liquidity": markets["total_liquidity"],
            "opportunities_detected": stats["opportunities"],
            "trades_executed": stats["trades"],
            "checks_performed": stats["checks"],
            "websocket_messages": stats["messages"],
            "last_update": datetime.now().isoformat(),
        }
    )


async def get_logs(request):
    """API to get latest logs."""
    logs = []

    try:
        if not LOG_FILE.exists():
            return web.json_response({"logs": ["日志文件不存在"]})

        # Read last 100 lines
        with open(LOG_FILE, 'r') as f:
            lines = f.readlines()

        # Get last 100 lines, strip whitespace
        logs = [line.strip() for line in lines[-100:] if line.strip()]

    except Exception as e:
        logs = [f"读取日志错误: {str(e)}"]

    return web.json_response({"logs": logs})


async def get_markets(request):
    """API to get subscribed markets."""
    try:
        if not MARKETS_FILE.exists():
            return web.json_response({"markets": [], "total": 0})

        with open(MARKETS_FILE, 'r') as f:
            markets = json.load(f)

        # Return top markets by volume
        sorted_markets = sorted(markets, key=lambda x: x.get('volume_24h', 0), reverse=True)

        return web.json_response({
            "markets": sorted_markets[:20],  # Top 20
            "total": len(markets),
        })

    except Exception as e:
        return web.json_response({"markets": [], "total": 0, "error": str(e)})


async def get_balance(request):
    """API to get wallet balance and position value."""
    try:
        # In dry-run mode, use simulated balance
        # In production, this would query Web3

        # For now, return default balance
        # TODO: Integrate with actual Web3 client
        balance_data = {
            "usdc_balance": 1000.00,  # Default starting balance
            "position_value": 0.00,    # Currently no open positions
            "total_assets": 1000.00,
            "pending_profit": 0.00,    # Unrealized profit
            "last_updated": datetime.now().isoformat(),
        }

        # Try to parse actual profit from logs
        stats = parse_log_stats()
        if stats["trades"] > 0:
            # In a real implementation, we'd calculate actual position value
            # For now, keep it simple
            pass

        return web.json_response(balance_data)

    except Exception as e:
        return web.json_response({
            "usdc_balance": 1000.00,
            "position_value": 0.00,
            "total_assets": 1000.00,
            "error": str(e)
        })


async def get_profit(request):
    """API to get profit statistics."""
    try:
        # Parse profit from log files
        total_profit = 0.0
        profit_history = []

        if LOG_FILE.exists():
            with open(LOG_FILE, 'r') as f:
                lines = f.readlines()

            # Look for profit information in logs
            for line in lines:
                if "预期利润:" in line:
                    # Extract profit value
                    match = re.search(r'预期利润:\s*\$([\d.]+)', line)
                    if match:
                        profit = float(match.group(1))
                        total_profit += profit

                        # Add to history
                        timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                        if timestamp_match:
                            profit_history.append({
                                "timestamp": timestamp_match.group(1),
                                "profit": profit
                            })

        return web.json_response({
            "total_profit": total_profit,
            "trade_count": len(profit_history),
            "profit_history": profit_history[-50:],  # Last 50 trades
            "avg_profit_per_trade": total_profit / len(profit_history) if profit_history else 0,
            "last_updated": datetime.now().isoformat(),
        })

    except Exception as e:
        return web.json_response({
            "total_profit": 0.0,
            "trade_count": 0,
            "profit_history": [],
            "avg_profit_per_trade": 0,
            "error": str(e)
        })


async def get_strategies(request):
    """API to get strategy status."""
    # TODO: Read from actual config
    # For now, return hardcoded status
    strategies = [
        {"id": "atomic_arbitrage", "name": "原子套利", "enabled": True, "icon": "⚡"},
        {"id": "negrisk", "name": "NegRisk", "enabled": True, "icon": "📊"},
        {"id": "market_grouper", "name": "组合套利", "enabled": True, "icon": "🔄"},
        {"id": "settlement_lag", "name": "结算滞后", "enabled": False, "icon": "⏰"},
        {"id": "market_making", "name": "盘口做市", "enabled": False, "icon": "💱"},
        {"id": "tail_risk", "name": "尾部风险", "enabled": False, "icon": "🛡️"},
    ]

    return web.json_response({"strategies": strategies})


async def toggle_strategy(request):
    """API to toggle strategy on/off."""
    strategy_id = request.match_info['strategy_id']

    # TODO: Actually toggle the strategy in config
    # For now, just return a success response

    # Find the strategy
    strategies = {
        "atomic_arbitrage": "原子套利",
        "negrisk": "NegRisk",
        "market_grouper": "组合套利",
        "settlement_lag": "结算滞后",
        "market_making": "盘口做市",
        "tail_risk": "尾部风险",
    }

    if strategy_id not in strategies:
        return web.json_response({
            "success": False,
            "error": "Unknown strategy"
        }, status=404)

    # Simulate toggle (in real implementation, would update config)
    # For now, just return the new state
    import random
    new_enabled = random.choice([True, False])

    return web.json_response({
        "success": True,
        "strategy_id": strategy_id,
        "strategy_name": strategies[strategy_id],
        "enabled": new_enabled,
        "message": f"{strategies[strategy_id]} 已{'启用' if new_enabled else '禁用'}",
        "last_updated": datetime.now().isoformat(),
    })


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
    """Serve the dashboard.html file."""
    return web.FileResponse(os.path.join(os.path.dirname(__file__), "static", "dashboard.html"))


def init_app():
    app = web.Application()

    # Routes
    app.router.add_get("/", index)
    app.router.add_get("/api/status", get_status)
    app.router.add_get("/api/logs", get_logs)
    app.router.add_get("/api/markets", get_markets)
    app.router.add_get("/api/opportunities", get_opportunities)

    # New API endpoints for balance, profit, and strategies
    app.router.add_get("/api/balance", get_balance)
    app.router.add_get("/api/profit", get_profit)
    app.router.add_get("/api/strategies", get_strategies)
    app.router.add_post("/api/strategies/{strategy_id}/toggle", toggle_strategy)

    # Static files
    static_path = os.path.join(os.path.dirname(__file__), "static")
    if not os.path.exists(static_path):
        os.makedirs(static_path)
    app.router.add_static("/static/", static_path)

    return app


if __name__ == "__main__":
    app = init_app()
    web.run_app(app, port=8080)
