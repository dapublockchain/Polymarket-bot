/**
 * APIHelper - Helper class for direct API calls and response mocking
 *
 * This class provides utilities for making direct API calls
 * and setting up response mocking for tests.
 */

import { Page, APIRequestContext, APIResponse } from '@playwright/test';

/**
 * Balance API response structure
 */
export interface BalanceResponse {
  usdc_balance: number;
  position_value: number;
  total_assets: number;
  pending_profit?: number;
  last_updated?: string;
  error?: string;
}

/**
 * Profit API response structure
 */
export interface ProfitResponse {
  total_profit: number;
  trade_count: number;
  profit_history: ProfitHistoryEntry[];
  avg_profit_per_trade: number;
  last_updated?: string;
  error?: string;
}

/**
 * Profit history entry
 */
export interface ProfitHistoryEntry {
  timestamp: string;
  profit: number;
}

/**
 * Strategy structure
 */
export interface Strategy {
  id: string;
  name: string;
  icon: string;
  enabled: boolean;
}

/**
 * Strategies API response structure
 */
export interface StrategiesResponse {
  strategies: Strategy[];
}

/**
 * Strategy toggle response structure
 */
export interface StrategyToggleResponse {
  success: boolean;
  strategy_id: string;
  strategy_name: string;
  enabled: boolean;
  message: string;
  last_updated?: string;
  error?: string;
}

/**
 * Status API response structure
 */
export interface StatusResponse {
  status: string;
  mode: string;
  uptime: string;
  subscribed_markets: number;
  opportunities_detected: number;
  trades_executed: number;
  last_updated?: string;
}

/**
 * Logs API response structure
 */
export interface LogsResponse {
  logs: string[];
}

/**
 * Opportunities API response structure
 */
export interface Opportunity {
  id: number;
  timestamp: string;
  pair: string;
  yes_price: number;
  no_price: number;
  profit: number;
  status: string;
}

export interface OpportunitiesResponse {
  opportunities: Opportunity[];
}

export class ApiHelper {
  readonly request: APIRequestContext;
  readonly baseURL: string;

  constructor(request: APIRequestContext, baseURL: string) {
    this.request = request;
    this.baseURL = baseURL;
  }

  // ===========================================================================
  // Direct API Call Methods
  // ===========================================================================

  /**
   * GET /api/balance - Fetch account balance
   */
  async getBalance(): Promise<BalanceResponse> {
    const response = await this.request.get(`${this.baseURL}/api/balance`);
    return await response.json() as BalanceResponse;
  }

  /**
   * GET /api/profit - Fetch profit statistics
   */
  async getProfit(): Promise<ProfitResponse> {
    const response = await this.request.get(`${this.baseURL}/api/profit`);
    return await response.json() as ProfitResponse;
  }

  /**
   * GET /api/strategies - Fetch all strategies
   */
  async getStrategies(): Promise<StrategiesResponse> {
    const response = await this.request.get(`${this.baseURL}/api/strategies`);
    return await response.json() as StrategiesResponse;
  }

  /**
   * POST /api/strategies/{id}/toggle - Toggle a strategy
   */
  async toggleStrategy(strategyId: string): Promise<StrategyToggleResponse> {
    const response = await this.request.post(`${this.baseURL}/api/strategies/${strategyId}/toggle`);
    return await response.json() as StrategyToggleResponse;
  }

  /**
   * GET /api/status - Fetch system status
   */
  async getStatus(): Promise<StatusResponse> {
    const response = await this.request.get(`${this.baseURL}/api/status`);
    return await response.json() as StatusResponse;
  }

  /**
   * GET /api/logs - Fetch system logs
   */
  async getLogs(): Promise<LogsResponse> {
    const response = await this.request.get(`${this.baseURL}/api/logs`);
    return await response.json() as LogsResponse;
  }

  /**
   * GET /api/opportunities - Fetch detected opportunities
   */
  async getOpportunities(): Promise<OpportunitiesResponse> {
    const response = await this.request.get(`${this.baseURL}/api/opportunities`);
    return await response.json() as OpportunitiesResponse;
  }

  // ===========================================================================
  // API Route Mocking Methods
  // ===========================================================================

  /**
   * Mock the balance API response
   */
  async mockBalance(page: Page, balance: Partial<BalanceResponse>): Promise<void> {
    await page.route('**/api/balance', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          usdc_balance: 1000.00,
          position_value: 0.00,
          total_assets: 1000.00,
          ...balance
        })
      });
    });
  }

  /**
   * Mock the profit API response
   */
  async mockProfit(page: Page, profit: Partial<ProfitResponse>): Promise<void> {
    await page.route('**/api/profit', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          total_profit: 0,
          trade_count: 0,
          profit_history: [],
          avg_profit_per_trade: 0,
          ...profit
        })
      });
    });
  }

  /**
   * Mock the strategies API response
   */
  async mockStrategies(page: Page, strategies: Strategy[]): Promise<void> {
    await page.route('**/api/strategies', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ strategies })
      });
    });
  }

  /**
   * Mock the strategy toggle API response
   */
  async mockStrategyToggle(page: Page, strategyId: string, enabled: boolean, success = true): Promise<void> {
    await page.route(`**/api/strategies/${strategyId}/toggle`, async route => {
      await route.fulfill({
        status: success ? 200 : 404,
        contentType: 'application/json',
        body: JSON.stringify({
          success,
          strategy_id: strategyId,
          strategy_name: 'Test Strategy',
          enabled,
          message: `Strategy ${enabled ? 'enabled' : 'disabled'}`
        })
      });
    });
  }

  /**
   * Mock the status API response
   */
  async mockStatus(page: Page, status: Partial<StatusResponse>): Promise<void> {
    await page.route('**/api/status', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: '在线',
          mode: 'dry-run',
          uptime: '0h 0m 0s',
          subscribed_markets: 0,
          opportunities_detected: 0,
          trades_executed: 0,
          ...status
        })
      });
    });
  }

  // ===========================================================================
  // Response Interception Utilities
  // ===========================================================================

  /**
   * Wait for and capture the next balance API call
   */
  async captureBalanceRequest(page: Page): Promise<{ url: string; method: string }> | null> {
    let captured: { url: string; method: string } | null = null;

    page.on('request', request => {
      if (request.url().includes('/api/balance')) {
        captured = {
          url: request.url(),
          method: request.method()
        };
      }
    });

    // Wait a bit for the request to be captured
    await page.waitForTimeout(100);

    return captured;
  }

  /**
   * Wait for and capture the next strategy toggle API call
   */
  async captureStrategyToggleRequest(page: Page, strategyId: string): Promise<{ url: string; method: string; body?: string }> | null> {
    let captured: { url: string; method: string; body?: string } | null = null;

    page.on('request', request => {
      if (request.url().includes(`/api/strategies/${strategyId}/toggle`)) {
        captured = {
          url: request.url(),
          method: request.method()
        };
      }
    });

    // Wait a bit for the request to be captured
    await page.waitForTimeout(100);

    return captured;
  }

  // ===========================================================================
  // Test Data Generators
  // ===========================================================================

  /**
   * Generate mock profit history
   */
  static generateProfitHistory(count: number, baseProfit = 100): ProfitHistoryEntry[] {
    const history: ProfitHistoryEntry[] = [];
    const now = new Date();

    for (let i = 0; i < count; i++) {
      const timestamp = new Date(now.getTime() - (count - i) * 60000); // 1-minute intervals
      history.push({
        timestamp: timestamp.toISOString().slice(0, 19).replace('T', ' '),
        profit: baseProfit + Math.random() * 50 - 20
      });
    }

    return history;
  }

  /**
   * Generate mock strategies
   */
  static generateMockStrategies(): Strategy[] {
    return [
      { id: 'atomic_arbitrage', name: '原子套利', icon: '⚡', enabled: true },
      { id: 'negrisk', name: 'NegRisk', icon: '📊', enabled: true },
      { id: 'market_grouper', name: '组合套利', icon: '🔄', enabled: true },
      { id: 'settlement_lag', name: '结算滞后', icon: '⏰', enabled: false },
      { id: 'market_making', name: '盘口做市', icon: '💱', enabled: false },
      { id: 'tail_risk', name: '尾部风险', icon: '🛡️', enabled: false },
    ];
  }

  /**
   * Generate mock opportunities
   */
  static generateMockOpportunities(count: number = 5): Opportunity[] {
    const opportunities: Opportunity[] = [];
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
}
