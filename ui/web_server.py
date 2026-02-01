#!/usr/bin/env python3
"""
PolyArb-X Web Server - 专业监控界面
"""
import os
import sys
import json
import asyncio
from datetime import datetime
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import TCPServer
from urllib.parse import parse_qs
import threading
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import ProfileManager
from src.api.profile_manager import ProfileManager

# Strategy state management
strategy_states = {
    'atomic': True,
    'negrisk': False,
    'combo': False,
    'settlement': False,
    'mmm': False,
    'tail': False
}

# Account balance (in dry-run mode, this is simulated)
account_balance = 10000.00

# Initialize ProfileManager
profile_manager = ProfileManager()

class PolyArbAPIHandler(SimpleHTTPRequestHandler):
    """Custom HTTP handler with API endpoints"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.dirname(os.path.abspath(__file__)), **kwargs)

    def do_GET(self):
        """Handle GET requests"""
        if self.path == '/api/status':
            self.send_json(self.get_status())
        elif self.path == '/api/metrics':
            self.send_json(self.get_metrics())
        elif self.path == '/api/logs':
            self.send_json(self.get_logs())
        elif self.path.startswith('/api/events'):
            self.send_json(self.get_events())
        elif self.path == '/api/health':
            self.send_json(self.get_health())
        elif self.path == '/api/strategies':
            self.send_json(self.get_strategies())
        elif self.path == '/api/balance':
            self.send_json(self.get_balance())
        elif self.path == '/api/profiles':
            self.send_json(self.get_profiles())
        elif self.path.startswith('/api/profiles/'):
            self.handle_profile_get()
        elif self.path == '/api/audit/config_changes':
            self.send_json(self.get_audit_history())
        elif self.path == '/':
            self.path = '/dashboard.html'
            super().do_GET()
        else:
            super().do_GET()

    def do_POST(self):
        """Handle POST requests"""
        if self.path == '/api/strategies':
            self.handle_strategies_post()
        elif self.path.startswith('/api/profiles/'):
            self.handle_profile_post()
        elif self.path == '/api/profiles/save':
            self.handle_save_profile()
        elif self.path == '/api/profiles/rollback':
            self.send_json(self.handle_rollback())
        else:
            self.send_response(404)
            self.end_headers()

    def send_json(self, data):
        """Send JSON response"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def get_status(self):
        """Get system status"""
        return {
            "status": "online",
            "mode": "dry-run",
            "websocket_connected": True,
            "uptime_seconds": int(time.time() - start_time),
            "last_update": datetime.now().isoformat()
        }

    def get_metrics(self):
        """Get performance metrics"""
        return {
            "total_trades": 0,
            "win_rate": 0.0,
            "net_profit": 0.0,
            "sharpe_ratio": 0.0,
            "profit_factor": 0.0,
            "max_drawdown": 0.0,
            "performance_history": []
        }

    def get_logs(self):
        """Get recent logs"""
        log_file = Path("../data/polyarb-x.log")
        if log_file.exists():
            with open(log_file, 'r') as f:
                lines = f.readlines()[-100:]  # Last 100 lines
            return {"logs": [line.strip() for line in lines if line.strip()]}
        return {"logs": []}

    def get_events(self):
        """Get recent trading events from events.jsonl"""
        try:
            from datetime import date

            # Get today's events file path
            events_dir = Path("../data/events")
            today = date.today()
            date_str = today.strftime("%Y%m%d")
            events_file = events_dir / date_str / "events.jsonl"

            if not events_file.exists():
                return {
                    "events": [],
                    "file_path": str(events_file),
                    "status": "no_file"
                }

            events = []
            with open(events_file, 'r') as f:
                # Read last 100 events
                lines = f.readlines()[-100:]

            for line in lines:
                line = line.strip()
                if line:
                    try:
                        event = json.loads(line)
                        events.append(event)
                    except json.JSONDecodeError:
                        continue

            return {
                "events": events,
                "file_path": str(events_file),
                "count": len(events),
                "status": "ok"
            }

        except Exception as e:
            return {
                "events": [],
                "error": str(e),
                "status": "error"
            }

    def get_health(self):
        """Health check for events system"""
        try:
            from datetime import date

            events_dir = Path("../data/events")
            today = date.today()
            date_str = today.strftime("%Y%m%d")
            events_file = events_dir / date_str / "events.jsonl"

            health = {
                "events_enabled": True,
                "events_file_exists": events_file.exists(),
                "events_file_path": str(events_file),
                "events_dir_exists": events_dir.exists()
            }

            if events_file.exists():
                # Count events
                with open(events_file, 'r') as f:
                    line_count = sum(1 for _ in f)
                health["total_events"] = line_count

            return health

        except Exception as e:
            return {
                "events_enabled": False,
                "error": str(e),
                "status": "error"
            }

    def get_strategies(self):
        """Get current strategy states"""
        return {
            "strategies": strategy_states,
            "status": "ok"
        }

    def get_balance(self):
        """Get account balance"""
        # In dry-run mode, return simulated balance
        # In live mode, this would fetch from blockchain/CEX
        return {
            "balance": f"{account_balance:.2f}",
            "currency": "USDC",
            "usage_percent": 0.0,  # Will be calculated from actual positions
            "status": "ok"
        }

    def handle_strategies_post(self):
        """Handle strategy toggle POST requests"""
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data)

            strategy = data.get('strategy')
            enabled = data.get('enabled')

            if strategy in strategy_states:
                strategy_states[strategy] = enabled
                print(f"[Strategy Toggle] {strategy}: {'ENABLED' if enabled else 'DISABLED'}")
                self.send_json({
                    "success": True,
                    "strategy": strategy,
                    "enabled": enabled
                })
            else:
                self.send_json({
                    "success": False,
                    "error": f"Unknown strategy: {strategy}"
                })
        except Exception as e:
            self.send_json({
                "success": False,
                "error": str(e)
            })

    # ========== Profile API Methods ==========

    def get_profiles(self):
        """Get all available profiles"""
        try:
            profiles = profile_manager.list_profiles()
            return {
                "profiles": profiles,
                "count": len(profiles),
                "status": "ok"
            }
        except Exception as e:
            return {
                "profiles": [],
                "error": str(e),
                "status": "error"
            }

    def handle_profile_get(self):
        """Handle GET /api/profiles/{name}"""
        try:
            # Extract profile name from path
            # Path format: /api/profiles/{name} or /api/profiles/{name}/apply
            path_parts = self.path.strip('/').split('/')
            if len(path_parts) >= 3:
                profile_name = path_parts[2]

                # Check if it's an apply request
                if len(path_parts) >= 4 and path_parts[3] == 'apply':
                    # Apply request should be POST, not GET
                    self.send_json({"error": "Use POST to apply profile"}, status=405)
                    return

                # Get profile details
                profile_data = profile_manager.get_profile(profile_name)
                self.send_json({
                    "profile": profile_data,
                    "status": "ok"
                })
            else:
                self.send_json({"error": "Invalid profile path"}, status=400)
        except ValueError as e:
            self.send_json({"error": str(e)}, status=404)
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)

    def handle_profile_post(self):
        """Handle POST /api/profiles/{name}/apply"""
        try:
            # Extract profile name from path
            path_parts = self.path.strip('/').split('/')
            if len(path_parts) >= 3:
                profile_name = path_parts[2]

                # Apply profile
                result = profile_manager.apply_profile(profile_name)

                print(f"[Profile Applied] {profile_name} by user")
                if result.get("risk_warnings"):
                    print(f"[Risk Warnings] {', '.join(result['risk_warnings'])}")

                self.send_json({
                    "success": True,
                    "result": result
                })
            else:
                self.send_json({"error": "Invalid profile path"}, status=400)
        except ValueError as e:
            self.send_json({
                "success": False,
                "error": str(e)
            }, status=400)
        except Exception as e:
            self.send_json({
                "success": False,
                "error": str(e)
            }, status=500)

    def handle_save_profile(self):
        """Handle POST /api/profiles/save"""
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data)

            name = data.get('name')
            description = data.get('description', '')
            tags = data.get('tags', [])
            config_override = data.get('config_override')

            if not name:
                self.send_json({
                    "success": False,
                    "error": "Profile name is required"
                }, status=400)
                return

            # Save custom profile
            result = profile_manager.save_custom_profile(
                name=name,
                description=description,
                tags=tags,
                config_override=config_override
            )

            print(f"[Profile Saved] custom/{name}")

            self.send_json({
                "success": True,
                "profile": result
            })
        except Exception as e:
            self.send_json({
                "success": False,
                "error": str(e)
            }, status=500)

    def handle_rollback(self):
        """Handle POST /api/profiles/rollback"""
        try:
            result = profile_manager.rollback()

            print(f"[Profile Rollback] Rolled back from {result.get('rolled_back_from')}")

            return {
                "success": True,
                "result": result
            }
        except ValueError as e:
            return {
                "success": False,
                "error": str(e)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def get_audit_history(self):
        """Handle GET /api/audit/config_changes"""
        try:
            from urllib.parse import parse_qs
            query = parse_qs(self.path.split('?')[1] if '?' in self.path else '')

            limit = int(query.get('limit', [200])[0])

            history = profile_manager.get_audit_history(limit=limit)

            return {
                "history": history,
                "count": len(history),
                "status": "ok"
            }
        except Exception as e:
            return {
                "history": [],
                "error": str(e),
                "status": "error"
            }

    def log_message(self, format, *args):
        """Suppress default logging"""
        if args[0] != 'GET /api/status' and args[0] != 'GET /api/metrics':
            super().log_message(format, *args)


def start_web_server(port=8080):
    """Start the web server"""
    global start_time
    start_time = time.time()

    print("=" * 60)
    print(" PolyArb-X Web监控界面")
    print("=" * 60)
    print(f"\n🚀 启动Web服务器...")
    print(f"📊 访问地址: http://localhost:{port}")
    print(f"🌐 网络地址: http://0.0.0.0:{port}")
    print(f"\n按 Ctrl+C 停止服务器\n")

    try:
        with TCPServer(("", port), PolyArbAPIHandler) as httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\n✅ 服务器已停止")
    except OSError as e:
        if e.errno == 48:  # Address already in use
            print(f"\n❌ 端口 {port} 已被占用")
            print(f"   请尝试其他端口或停止占用该端口的程序")
            print(f"\n   使用方式:")
            print(f"   python3 ui/web_server.py --port 8081")
        else:
            print(f"\n❌ 错误: {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PolyArb-X Web监控界面")
    parser.add_argument("--port", type=int, default=8080, help="端口号 (默认: 8080)")
    args = parser.parse_args()

    start_web_server(args.port)
