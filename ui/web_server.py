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
        elif self.path == '/':
            self.path = '/dashboard.html'
            super().do_GET()
        else:
            super().do_GET()

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
