/**
 * Test Data Fixtures
 *
 * Shared test data and utilities for E2E tests
 */

import { DashboardPage } from '../pages/DashboardPage';
import { ApiHelper, Strategy, ProfitHistoryEntry } from '../pages/ApiHelper';

/**
 * Default strategy configurations
 */
export const DEFAULT_STRATEGIES: Strategy[] = [
  { id: 'atomic_arbitrage', name: '原子套利', icon: '⚡', enabled: true },
  { id: 'negrisk', name: 'NegRisk', icon: '📊', enabled: true },
  { id: 'market_grouper', name: '组合套利', icon: '🔄', enabled: true },
  { id: 'settlement_lag', name: '结算滞后', icon: '⏰', enabled: false },
  { id: 'market_making', name: '盘口做市', icon: '💱', enabled: false },
  { id: 'tail_risk', name: '尾部风险', icon: '🛡️', enabled: false },
];

/**
 * Default balance data
 */
export const DEFAULT_BALANCE = {
  usdc_balance: 1000.00,
  position_value: 0.00,
  total_assets: 1000.00,
  pending_profit: 0.00,
};

/**
 * Default profit data
 */
export const DEFAULT_PROFIT = {
  total_profit: 0.0,
  trade_count: 0,
  profit_history: [] as ProfitHistoryEntry[],
  avg_profit_per_trade: 0.0,
};

/**
 * Default system status
 */
export const DEFAULT_STATUS = {
  status: '在线',
  mode: 'dry-run',
  uptime: '0h 0m 0s',
  subscribed_markets: 2,
  opportunities_detected: 0,
  trades_executed: 0,
};

/**
 * Generate test profit history
 */
export function generateTestProfitHistory(count: number, baseValue: number = 100): ProfitHistoryEntry[] {
  const history: ProfitHistoryEntry[] = [];
  const now = new Date();

  for (let i = 0; i < count; i++) {
    const timestamp = new Date(now.getTime() - (count - i) * 60000);
    history.push({
      timestamp: timestamp.toISOString().slice(0, 19).replace('T', ' '),
      profit: baseValue + (Math.random() - 0.5) * 20
    });
  }

  return history;
}

/**
 * Generate test opportunities
 */
export function generateTestOpportunities(count: number = 5) {
  const opportunities = [];
  const pairs = ['Trump vs Harris', 'FED Rate Cut', 'Bitcoin 100k', 'Ethereum ETF', 'Solana Flip'];
  const statuses = ['已执行', '已忽略 (利润过低)', '等待执行'];

  for (let i = 0; i < count; i++) {
    opportunities.push({
      id: i + 1,
      timestamp: new Date().toISOString().slice(11, 19),
      pair: pairs[i % pairs.length],
      yes_price: 0.3 + Math.random() * 0.4,
      no_price: 0.5 + Math.random() * 0.4,
      profit: Math.random() * 10 - 2,
      status: statuses[i % statuses.length]
    });
  }

  return opportunities;
}

/**
 * Generate test logs
 */
export function generateTestLogs(count: number = 20): string[] {
  const logs = [];
  const levels = ['INFO', 'ERROR', 'WARN', 'DEBUG'];
  const messages = [
    '检测到套利机会',
    '执行交易',
    'WebSocket连接成功',
    '订单本更新',
    '市场数据同步',
    '策略检查完成'
  ];

  const now = new Date();

  for (let i = 0; i < count; i++) {
    const timestamp = new Date(now.getTime() - (count - i) * 5000);
    const level = levels[i % levels.length];
    const message = messages[i % messages.length];
    logs.push(`${timestamp.toISOString().slice(0, 19).replace('T', ' ')}|${level}|${message}`);
  }

  return logs;
}

/**
 * Mock API responses helper
 */
export class MockApiHelper {
  /**
   * Setup all default API mocks
   */
  static setupDefaultMocks(page: any) {
    // Mock balance
    page.route('**/api/balance', async (route: any) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(DEFAULT_BALANCE)
      });
    });

    // Mock profit
    page.route('**/api/profit', async (route: any) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(DEFAULT_PROFIT)
      });
    });

    // Mock strategies
    page.route('**/api/strategies', async (route: any) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ strategies: DEFAULT_STRATEGIES })
      });
    });

    // Mock status
    page.route('**/api/status', async (route: any) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(DEFAULT_STATUS)
      });
    });

    // Mock logs
    page.route('**/api/logs', async (route: any) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ logs: generateTestLogs(10) })
      });
    });

    // Mock opportunities
    page.route('**/api/opportunities', async (route: any) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ opportunities: generateTestOpportunities(3) })
      });
    });
  }

  /**
   * Setup strategy toggle mock
   */
  static setupStrategyToggleMock(page: any, strategyId: string, enabled: boolean) {
    page.route(`**/api/strategies/${strategyId}/toggle`, async (route: any) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          strategy_id: strategyId,
          strategy_name: 'Test Strategy',
          enabled: enabled,
          message: `Strategy ${enabled ? 'enabled' : 'disabled'}`
        })
      });
    });
  }
}

/**
 * Test timeouts
 */
export const TEST_TIMEOUTS = {
  SHORT: 1000,
  MEDIUM: 2000,
  LONG: 5000,
  CHART_RENDER: 500,
  API_CALL: 3000,
  TOAST_APPEAR: 1000,
  TOAST_DISAPPEAR: 3500,
};

/**
 * Retry helper for flaky tests
 */
export async function retry<T>(
  fn: () => Promise<T>,
  maxRetries: number = 3,
  delay: number = 1000
): Promise<T> {
  let lastError: Error | undefined;

  for (let i = 0; i < maxRetries; i++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error as Error;
      if (i < maxRetries - 1) {
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
  }

  throw lastError;
}
