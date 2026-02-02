#!/usr/bin/env python3
"""
PolyArb-X Production Daily Report Generator

生成每日运行报告，包括：
- 运行模式与配置
- 交易统计
- 订单执行
- 延迟统计
- 告警汇总
- 异常诊断

Usage:
    python3 scripts/production_daily_report.py [--date YYYYMMDD]
"""

import argparse
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any

# ============================================================
# 配置
# ============================================================

REPORTS_DIR = Path("reports/daily")
EVENTS_FILE = Path("data/events.jsonl")
ALERTS_FILE = Path("data/alerts/alerts.jsonl")
ALERTS_STATE_FILE = Path("data/alerts/alerts_state.json")
CONFIG_FILE = Path("config/config.yaml")


# ============================================================
# 工具函数
# ============================================================

def read_jsonl(file_path: Path) -> List[Dict]:
    """读取 JSONL 文件"""
    if not file_path.exists():
        return []

    data = []
    with open(file_path, 'r') as f:
        for line in f:
            if line.strip():
                try:
                    data.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return data


def filter_by_date(events: List[Dict], date_str: str) -> List[Dict]:
    """按日期过滤事件"""
    target_date = date_str[:8]  # YYYYMMDD
    filtered = []

    for event in events:
        timestamp = event.get("timestamp", "")
        if timestamp.startswith(target_date):
            filtered.append(event)

    return filtered


def calculate_percent(numerator: int, denominator: int) -> float:
    """计算百分比"""
    if denominator == 0:
        return 0.0
    return (numerator / denominator) * 100


def calculate_percentile(values: List[float], percentile: float) -> float:
    """计算百分位数"""
    if not values:
        return 0.0

    sorted_values = sorted(values)
    k = (len(sorted_values) - 1) * percentile / 100
    f = int(k)
    c = f + 1

    if c >= len(sorted_values):
        return sorted_values[-1]

    return sorted_values[f] + (k - f) * (sorted_values[c] - sorted_values[f])


# ============================================================
# 报告生成器
# ============================================================

def generate_report(date_str: str = None) -> str:
    """生成每日报告"""

    # 默认使用今天
    if date_str is None:
        date_str = datetime.now().strftime("%Y%m%d")

    # 读取数据
    all_events = read_jsonl(EVENTS_FILE)
    day_events = filter_by_date(all_events, date_str)

    all_alerts = read_jsonl(ALERTS_FILE)
    day_alerts = filter_by_date(all_alerts, date_str)

    # 读取当前告警状态
    current_alerts = []
    if ALERTS_STATE_FILE.exists():
        with open(ALERTS_STATE_FILE, 'r') as f:
            try:
                state = json.load(f)
                current_alerts = state.get("alerts", [])
            except json.JSONDecodeError:
                pass

    # 读取配置
    config = {}
    if CONFIG_FILE.exists():
        try:
            import yaml
            with open(CONFIG_FILE, 'r') as f:
                config = yaml.safe_load(f)
        except ImportError:
            pass
        except Exception:
            pass

    # ========================================================
    # 统计数据
    # ========================================================

    # 交易统计
    opportunities = [e for e in day_events if e.get("event_type") == "opportunity"]
    fills = [e for e in day_events if e.get("event_type") == "fill"]

    total_opportunities = len(opportunities)
    total_fills = len(fills)

    # PnL 统计
    total_pnl = sum(float(f.get("realized_pnl", 0)) for f in fills)
    expected_pnl = sum(float(o.get("expected_profit", 0)) for o in opportunities)

    # 订单执行统计
    order_submitted = [e for e in day_events if e.get("event_type") == "order_submitted"]
    order_rejected = [e for e in day_events if e.get("event_type") == "order_rejected"]

    total_submitted = len(order_submitted) + len(order_rejected)
    total_rejected = len(order_rejected)
    total_executed = total_fills

    reject_rate = calculate_percent(total_rejected, total_submitted) if total_submitted > 0 else 0
    fill_rate = calculate_percent(total_executed, total_submitted) if total_submitted > 0 else 0

    # 延迟统计
    latencies = []
    for event in day_events:
        if "latency_ms" in event:
            latencies.append(float(event["latency_ms"]))
        elif "latency" in event:
            latencies.append(float(event["latency"]))

    p50_latency = calculate_percentile(latencies, 50) if latencies else 0
    p95_latency = calculate_percentile(latencies, 95) if latencies else 0
    p99_latency = calculate_percentile(latencies, 99) if latencies else 0

    # 告警统计
    critical_alerts = [a for a in current_alerts if a.get("severity") == "CRITICAL" and a.get("state") == "FIRING"]
    warning_alerts = [a for a in current_alerts if a.get("severity") == "WARNING" and a.get("state") == "FIRING"]

    # ========================================================
    # 生成报告内容
    # ========================================================

    dry_run = config.get("DRY_RUN", True)
    profile_name = config.get("PROFILE_NAME", "unknown")

    report_lines = [
        f"# Daily Report {date_str}",
        "",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "---",
        "",
        "## 运行模式",
        f"- **Mode:** {'Shadow (DRY_RUN)' if dry_run else 'Live (REAL MONEY)'}",
        f"- **Profile:** {profile_name}",
        "",
        "---",
        "",
        "## 交易统计",
        f"- **总交易数:** {total_fills}",
        f"- **总机会数:** {total_opportunities}",
        f"- **胜率:** {calculate_percent(total_fills, total_opportunities):.1f}%" if total_opportunities > 0 else "- **胜率:** N/A",
        f"- **实现盈亏:** ${total_pnl:.2f}",
        f"- **预期盈亏:** ${expected_pnl:.2f}",
        "",
        "---",
        "",
        "## 订单执行",
        f"- **提交订单:** {total_submitted}",
        f"- **成交订单:** {total_executed}",
        f"- **拒绝订单:** {total_rejected}",
        f"- **拒绝率:** {reject_rate:.1f}%",
        f"- **成交率:** {fill_rate:.1f}%",
        "",
        "---",
        "",
        "## 延迟统计",
        f"- **P50:** {p50_latency:.0f}ms",
        f"- **P95:** {p95_latency:.0f}ms",
        f"- **P99:** {p99_latency:.0f}ms",
        "",
        "---",
        "",
        "## 告警汇总",
        f"- **活跃告警:** {len(critical_alerts) + len(warning_alerts)}",
        f"- **CRITICAL:** {len(critical_alerts)}",
        f"- **WARNING:** {len(warning_alerts)}",
        "",
    ]

    # 列出活跃告警
    if critical_alerts or warning_alerts:
        report_lines.append("### 活跃告警详情")
        report_lines.append("")

        for alert in critical_alerts + warning_alerts:
            alert_id = alert.get("id", "unknown")
            alert_name = alert.get("name", "Unknown")
            severity = alert.get("severity", "UNKNOWN")
            report_lines.append(f"- **{alert_id}** ({severity}): {alert_name}")

        report_lines.append("")

    # 告警历史
    if day_alerts:
        report_lines.append("### 今日告警历史")
        report_lines.append("")

        # 按告警 ID 分组
        alert_counts = {}
        for alert in day_alerts:
            alert_id = alert.get("alert_id", "unknown")
            if alert_id not in alert_counts:
                alert_counts[alert_id] = 0
            alert_counts[alert_id] += 1

        for alert_id, count in sorted(alert_counts.items(), key=lambda x: x[1], reverse=True):
            report_lines.append(f"- **{alert_id}:** {count} 次触发")

        report_lines.append("")

    # ========================================================
    # 异常诊断
    # ========================================================

    report_lines.append("---")
    report_lines.append("")
    report_lines.append("## 异常诊断")
    report_lines.append("")

    issues = []

    # 高拒绝率
    if reject_rate > 10:
        issues.append(f"⚠️ 拒绝率过高 ({reject_rate:.1f}%)，可能需要调整滑点或 Gas 价格")

    # 低成交率
    if fill_rate < 30 and total_submitted > 10:
        issues.append(f"⚠️ 成交率过低 ({fill_rate:.1f}%)，可能原因：滑点过严、Gas 不足")

    # 高延迟
    if p95_latency > 500:
        issues.append(f"⚠️ P95 延迟过高 ({p95_latency:.0f}ms)，可能影响交易执行")

    # 负盈亏
    if total_pnl < 0:
        issues.append(f"⚠️ 今日亏损 ${total_pnl:.2f}")

    # CRITICAL 告警
    if critical_alerts:
        critical_ids = [a.get("id") for a in critical_alerts]
        issues.append(f"🚨 存在 CRITICAL 告警: {', '.join(critical_ids)}")

    if issues:
        report_lines.extend(issues)
    else:
        report_lines.append("✅ 无异常")

    report_lines.append("")
    report_lines.append("---")
    report_lines.append("")
    report_lines.append("**报告结束**")

    return "\n".join(report_lines)


def main():
    """主函数"""

    parser = argparse.ArgumentParser(description="生成 PolyArb-X 每日报告")
    parser.add_argument("--date", type=str, help="日期 (YYYYMMDD)，默认为今天")
    parser.add_argument("--output", type=str, help="输出文件路径，默认为 reports/daily/YYYYMMDD.md")

    args = parser.parse_args()

    # 确定日期
    date_str = args.date if args.date else datetime.now().strftime("%Y%m%d")

    # 生成报告
    report = generate_report(date_str)

    # 确定输出路径
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = REPORTS_DIR / f"{date_str}.md"

    # 创建目录
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 写入报告
    with open(output_path, 'w') as f:
        f.write(report)

    print(f"✅ Report generated: {output_path}")
    print(f"   Date: {date_str}")
    print(f"   Size: {len(report)} bytes")


if __name__ == "__main__":
    main()
