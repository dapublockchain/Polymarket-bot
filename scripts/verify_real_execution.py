#!/usr/bin/env python3
"""
验证脚本：检查实盘交易模式是否正确配置

使用方法:
    python3 scripts/verify_real_execution.py
"""
import sys
import re
from pathlib import Path


def check_file(filepath: str, search_pattern: str, context_lines: int = 3) -> bool:
    """
    检查文件中是否包含指定的模式

    Args:
        filepath: 文件路径
        search_pattern: 正则表达式模式
        context_lines: 显示上下文行数

    Returns:
        True 如果找到模式
    """
    try:
        with open(filepath, 'r') as f:
            lines = f.readlines()

        for i, line in enumerate(lines):
            if re.search(search_pattern, line):
                # 显示上下文
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)
                print(f"✅ 找到匹配 (行 {i+1}):")
                for j in range(start, end):
                    prefix = ">>> " if j == i else "    "
                    print(f"{prefix}{j+1:4d} | {lines[j]}", end='')
                print()
                return True

        return False

    except FileNotFoundError:
        print(f"❌ 文件未找到: {filepath}")
        return False


def main():
    """主检查逻辑"""
    print("=" * 70)
    print("🔍 PolyArb-X 实盘交易模式验证")
    print("=" * 70)
    print()

    all_passed = True

    # 检查 1: main.py 中 LiveExecutor 初始化
    print("检查 1: LiveExecutor 初始化")
    print("-" * 70)
    if not check_file(
        "src/main.py",
        r'use_real_execution\s*=\s*True',
        context_lines=5
    ):
        print("❌ 未找到 'use_real_execution=True'")
        print("   LiveExecutor 可能仍在使用模拟执行!")
        all_passed = False
    print()

    # 检查 2: main.py 中实盘模式执行逻辑
    print("检查 2: 实盘模式交易执行")
    print("-" * 70)
    if not check_file(
        "src/main.py",
        r'execution_router\.execute_arbitrage',
        context_lines=5
    ):
        print("❌ 未找到 'execution_router.execute_arbitrage' 在实盘模式分支")
        print("   实盘模式可能没有实际执行交易!")
        all_passed = False
    print()

    # 检查 3: LiveExecutor 中的 use_real_execution 参数
    print("检查 3: LiveExecutor 参数定义")
    print("-" * 70)
    if not check_file(
        "src/execution/live_executor.py",
        r'use_real_execution:\s*bool\s*=\s*False',
        context_lines=3
    ):
        print("⚠️  LiveExecutor 可能没有定义 use_real_execution 参数")
    else:
        print("✅ LiveExecutor 定义了 use_real_execution 参数")
    print()

    # 检查 4: live_executor.py 中的真实执行逻辑
    print("检查 4: 真实执行逻辑 (_execute_real_arbitrage)")
    print("-" * 70)
    if not check_file(
        "src/execution/live_executor.py",
        r'_execute_real_arbitrage',
        context_lines=3
    ):
        print("❌ 未找到 '_execute_real_arbitrage' 方法")
        print("   真实执行逻辑可能未实现!")
        all_passed = False
    print()

    # 检查 5: 配置文件
    print("检查 5: 配置文件 (config/config.yaml)")
    print("-" * 70)
    try:
        with open("config/config.yaml", 'r') as f:
            config = f.read()
            if re.search(r'DRY_RUN:\s*false', config):
                print("✅ DRY_RUN: false (实盘模式)")
            else:
                print("❌ DRY_RUN 未设置为 false")
                all_passed = False
    except FileNotFoundError:
        print("❌ 配置文件未找到")
        all_passed = False
    print()

    # 总结
    print("=" * 70)
    if all_passed:
        print("✅ 所有检查通过！实盘交易模式配置正确")
        print()
        print("下一步:")
        print("1. 重启系统: pkill -f 'python3 src/main.py' && python3 src/main.py")
        print("2. 监控日志: tail -f data/polyarb-x.log")
        print("3. 确认日志显示:")
        print("   - '🔴 LiveExecutor initialized (REAL TRADING MODE - use_real_execution=True)'")
        print("   - '🔴 REAL EXECUTION - Using CLOB API'")
        return 0
    else:
        print("❌ 部分检查失败！请检查上述问题")
        print()
        print("可能的问题:")
        print("1. main.py 未设置 use_real_execution=True")
        print("2. 实盘模式分支未调用 execution_router")
        print("3. 配置文件 DRY_RUN 仍为 true")
        return 1


if __name__ == "__main__":
    sys.exit(main())
