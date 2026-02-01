/**
 * DashboardPage - Page Object Model for PolyArb-X Dashboard
 *
 * This class encapsulates all interactions with the dashboard page,
 * providing a clean API for tests to interact with the UI.
 */

import { Page, Locator, expect } from '@playwright/test';

/**
 * Interface for Balance data from API
 */
export interface BalanceData {
  usdc_balance: number;
  position_value: number;
  total_assets: number;
  pending_profit?: number;
  last_updated?: string;
}

/**
 * Interface for Profit data from API
 */
export interface ProfitData {
  total_profit: number;
  trade_count: number;
  profit_history: Array<{ timestamp: string; profit: number }>;
  avg_profit_per_trade: number;
  last_updated?: string;
}

/**
 * Interface for Strategy data from API
 */
export interface Strategy {
  id: string;
  name: string;
  icon: string;
  enabled: boolean;
}

/**
 * Interface for System Status data from API
 */
export interface SystemStatus {
  status: string;
  mode: string;
  uptime: string;
  subscribed_markets: number;
  opportunities_detected: number;
  trades_executed: number;
  last_updated?: string;
}

export class DashboardPage {
  readonly page: Page;

  // Header locators
  readonly logo: Locator;
  readonly title: Locator;
  readonly version: Locator;
  readonly statusDot: Locator;
  readonly statusText: Locator;
  readonly uptime: Locator;
  readonly refreshButton: Locator;

  // Account Balance Card locators
  readonly accountBalanceCard: Locator;
  readonly accountBalanceValue: Locator;
  readonly accountBalanceLabel: Locator;

  // Position Value Card locators
  readonly positionValueCard: Locator;
  readonly positionValueValue: Locator;
  readonly positionValueLabel: Locator;

  // Total Profit Card locators
  readonly totalProfitCard: Locator;
  readonly totalProfitValue: Locator;
  readonly totalProfitLabel: Locator;

  // Total Assets Card locators
  readonly totalAssetsCard: Locator;
  readonly totalAssetsValue: Locator;
  readonly totalAssetsLabel: Locator;

  // Secondary metrics
  readonly totalOpportunities: Locator;
  readonly totalTrades: Locator;
  readonly avgProfit: Locator;
  readonly successRate: Locator;

  // Strategy Grid locators
  readonly strategiesSection: Locator;
  readonly strategiesGrid: Locator;
  readonly strategyCards: Locator;

  // Performance Chart
  readonly performanceChart: Locator;
  readonly chartPeriodSelect: Locator;

  // Recent Trades Table
  readonly tradesTable: Locator;
  readonly tradesTableBody: Locator;
  readonly tradesTableHeaders: Locator;

  // System Status Panel
  readonly systemStatusPanel: Locator;
  readonly runModeBadge: Locator;
  readonly subscribedMarkets: Locator;
  readonly orderbookUpdates: Locator;
  readonly circuitTrips: Locator;
  readonly anomalyDetections: Locator;

  // Live Logs
  readonly logsContainer: Locator;
  readonly logsPanel: Locator;

  // Signals List
  readonly signalsList: Locator;
  readonly signalsPanel: Locator;

  // Toast notifications
  readonly toastContainer: Locator;

  constructor(page: Page) {
    this.page = page;

    // Initialize Header locators
    this.logo = page.locator('.header .w-10.h-10.bg-gradient-to-br');
    this.title = page.locator('h1.text-xl');
    this.version = page.locator('.header p.text-xs');
    this.statusDot = page.locator('.pulse-dot');
    this.statusText = page.locator('#status-text');
    this.uptime = page.locator('#uptime');
    this.refreshButton = page.locator('button:has-text("刷新")');

    // Initialize Account Balance Card locators
    this.accountBalanceCard = page.locator('.metric-card').filter({ hasText: '账户余额' });
    this.accountBalanceValue = page.locator('#account-balance');
    this.accountBalanceLabel = page.locator('.metric-card').filter({ hasText: '账户余额' }).locator('.text-slate-400.text-sm');

    // Initialize Position Value Card locators
    this.positionValueCard = page.locator('.metric-card').filter({ hasText: '持仓价值' });
    this.positionValueValue = page.locator('#position-value');
    this.positionValueLabel = page.locator('.metric-card').filter({ hasText: '持仓价值' }).locator('.text-slate-400.text-sm');

    // Initialize Total Profit Card locators
    this.totalProfitCard = page.locator('.metric-card').filter({ hasText: '总利润' });
    this.totalProfitValue = page.locator('#total-profit');
    this.totalProfitLabel = page.locator('.metric-card').filter({ hasText: '总利润' }).locator('.text-slate-400.text-sm');

    // Initialize Total Assets Card locators
    this.totalAssetsCard = page.locator('.metric-card').filter({ hasText: '总资产' });
    this.totalAssetsValue = page.locator('#total-assets');
    this.totalAssetsLabel = page.locator('.metric-card').filter({ hasText: '总资产' }).locator('.text-slate-400.text-sm');

    // Initialize Secondary metrics
    this.totalOpportunities = page.locator('#total-opportunities');
    this.totalTrades = page.locator('#total-trades');
    this.avgProfit = page.locator('#avg-profit');
    this.successRate = page.locator('#success-rate');

    // Initialize Strategy Grid locators
    this.strategiesSection = page.locator('.glass-card').filter({ hasText: '策略状态' });
    this.strategiesGrid = page.locator('#strategies-grid');
    this.strategyCards = this.strategiesGrid.locator('.bg-slate-800\\/50');

    // Initialize Performance Chart
    this.performanceChart = page.locator('#performance-chart');
    this.chartPeriodSelect = page.locator('#chart-period');

    // Initialize Recent Trades Table
    this.tradesTable = page.locator('.glass-card').filter({ hasText: '最近交易' }).locator('table');
    this.tradesTableBody = page.locator('#trades-table');
    this.tradesTableHeaders = this.tradesTable.locator('thead th');

    // Initialize System Status Panel
    this.systemStatusPanel = page.locator('.glass-card').filter({ hasText: '系统状态' });
    this.runModeBadge = page.locator('#run-mode');
    this.subscribedMarkets = page.locator('#subscribed-markets');
    this.orderbookUpdates = page.locator('#orderbook-updates');
    this.circuitTrips = page.locator('#circuit-trips');
    this.anomalyDetections = page.locator('#anomaly-detections');

    // Initialize Live Logs
    this.logsPanel = page.locator('.glass-card').filter({ hasText: '系统日志' });
    this.logsContainer = page.locator('#logs-container');

    // Initialize Signals List
    this.signalsPanel = page.locator('.glass-card').filter({ hasText: '最新信号' });
    this.signalsList = page.locator('#signals-list');

    // Toast notifications (will be created dynamically)
    this.toastContainer = page.locator('body');
  }

  // ===========================================================================
  // Navigation Methods
  // ===========================================================================

  /**
   * Navigate to the dashboard
   */
  async goto(): Promise<void> {
    await this.page.goto('/');
    await this.page.waitForLoadState('networkidle');
    await this.waitForDashboardToLoad();
  }

  /**
   * Wait for dashboard to fully load
   */
  async waitForDashboardToLoad(): Promise<void> {
    // Wait for key elements to be visible
    await this.accountBalanceValue.waitFor({ state: 'visible' });
    await this.totalProfitValue.waitFor({ state: 'visible' });
    await this.strategiesGrid.waitFor({ state: 'visible' });
  }

  /**
   * Reload the page
   */
  async reload(): Promise<void> {
    await this.page.reload();
    await this.waitForDashboardToLoad();
  }

  // ===========================================================================
  // API Response Interception Methods
  // ===========================================================================

  /**
   * Intercept and wait for balance API response
   */
  async waitForBalanceAPI(): Promise<any> {
    const [response] = await Promise.all([
      this.page.waitForResponse(resp => resp.url().includes('/api/balance')),
      // The API call happens automatically, so we just wait for it
    ]);
    return await response.json();
  }

  /**
   * Intercept and wait for profit API response
   */
  async waitForProfitAPI(): Promise<any> {
    const [response] = await Promise.all([
      this.page.waitForResponse(resp => resp.url().includes('/api/profit')),
    ]);
    return await response.json();
  }

  /**
   * Intercept and wait for strategies API response
   */
  async waitForStrategiesAPI(): Promise<any> {
    const [response] = await Promise.all([
      this.page.waitForResponse(resp => resp.url().includes('/api/strategies')),
    ]);
    return await response.json();
  }

  /**
   * Intercept and wait for strategy toggle API response
   */
  async waitForStrategyToggleAPI(strategyId: string): Promise<any> {
    const [response] = await Promise.all([
      this.page.waitForResponse(resp =>
        resp.url().includes(`/api/strategies/${strategyId}/toggle`) &&
        resp.request().method() === 'POST'
      ),
    ]);
    return await response.json();
  }

  /**
   * Intercept and wait for status API response
   */
  async waitForStatusAPI(): Promise<any> {
    const [response] = await Promise.all([
      this.page.waitForResponse(resp => resp.url().includes('/api/status')),
    ]);
    return await response.json();
  }

  // ===========================================================================
  // Account Balance Card Methods
  // ===========================================================================

  /**
   * Get the current account balance value
   */
  async getAccountBalance(): Promise<string> {
    return await this.accountBalanceValue.textContent() || '';
  }

  /**
   * Get account balance as a number
   */
  async getAccountBalanceValue(): Promise<number> {
    const text = await this.getAccountBalance();
    return parseFloat(text.replace('$', '').replace(/,/g, ''));
  }

  /**
   * Wait for account balance to update
   */
  async waitForAccountBalanceUpdate(): Promise<void> {
    await this.page.waitForResponse(resp => resp.url().includes('/api/balance'));
  }

  // ===========================================================================
  // Position Value Card Methods
  // ===========================================================================

  /**
   * Get the current position value
   */
  async getPositionValue(): Promise<string> {
    return await this.positionValueValue.textContent() || '';
  }

  /**
   * Get position value as a number
   */
  async getPositionValueNumber(): Promise<number> {
    const text = await this.getPositionValue();
    return parseFloat(text.replace('$', '').replace(/,/g, ''));
  }

  // ===========================================================================
  // Total Profit Card Methods
  // ===========================================================================

  /**
   * Get the current total profit
   */
  async getTotalProfit(): Promise<string> {
    return await this.totalProfitValue.textContent() || '';
  }

  /**
   * Get total profit as a number
   */
  async getTotalProfitValue(): Promise<number> {
    const text = await this.getTotalProfit();
    return parseFloat(text.replace('$', '').replace(/,/g, ''));
  }

  // ===========================================================================
  // Total Assets Card Methods
  // ===========================================================================

  /**
   * Get the current total assets
   */
  async getTotalAssets(): Promise<string> {
    return await this.totalAssetsValue.textContent() || '';
  }

  /**
   * Get total assets as a number
   */
  async getTotalAssetsValue(): Promise<number> {
    const text = await this.getTotalAssets();
    return parseFloat(text.replace('$', '').replace(/,/g, ''));
  }

  /**
   * Verify total assets equals balance + position value
   */
  async verifyTotalAssetsCalculation(): Promise<boolean> {
    const balance = await this.getAccountBalanceValue();
    const positionValue = await this.getPositionValueNumber();
    const totalAssets = await this.getTotalAssetsValue();

    const expectedTotal = balance + positionValue;
    // Allow small floating point differences
    return Math.abs(totalAssets - expectedTotal) < 0.01;
  }

  // ===========================================================================
  // Strategy Methods
  // ===========================================================================

  /**
   * Get all strategy cards
   */
  getStrategyCards(): Locator {
    return this.strategyCards;
  }

  /**
   * Get strategy card by ID
   */
  getStrategyCardById(strategyId: string): Locator {
    return this.page.locator(`#strategy-card-${strategyId}`);
  }

  /**
   * Get strategy card by name
   */
  getStrategyCardByName(name: string): Locator {
    return this.strategyCards.filter({ hasText: name });
  }

  /**
   * Get the status badge of a strategy
   */
  getStrategyStatusBadge(strategyId: string): Locator {
    return this.page.locator(`#strategy-${strategyId}-status`);
  }

  /**
   * Check if a strategy is enabled (has ring-2 ring-green-500/30 class)
   */
  async isStrategyEnabled(strategyId: string): Promise<boolean> {
    const card = this.getStrategyCardById(strategyId);
    const classList = await card.getAttribute('class') || '';
    return classList.includes('ring-2') && classList.includes('ring-green-500');
  }

  /**
   * Toggle a strategy on/off by clicking it
   */
  async toggleStrategy(strategyId: string): Promise<any> {
    const card = this.getStrategyCardById(strategyId);

    // Get enabled state before toggle
    const wasEnabled = await this.isStrategyEnabled(strategyId);

    // Click the card
    await card.click();

    // Wait for API response
    const response = await this.waitForStrategyToggleAPI(strategyId);

    // Wait for visual update
    await this.page.waitForTimeout(500);

    return {
      wasEnabled,
      response,
      isNowEnabled: await this.isStrategyEnabled(strategyId)
    };
  }

  /**
   * Get all strategies with their states
   */
  async getAllStrategies(): Promise<Array<{ id: string; name: string; enabled: boolean }>> {
    const cards = this.strategyCards;
    const count = await cards.count();
    const strategies: Array<{ id: string; name: string; enabled: boolean }> = [];

    for (let i = 0; i < count; i++) {
      const card = cards.nth(i);
      const id = await card.getAttribute('id');
      const name = await card.locator('.text-sm.font-medium').textContent();
      const statusText = await card.locator('[id*="strategy-"][id*="-status"]').textContent();
      const enabled = statusText?.includes('启用') || false;

      if (id) {
        strategies.push({
          id: id.replace('strategy-card-', ''),
          name: name || '',
          enabled
        });
      }
    }

    return strategies;
  }

  /**
   * Get the count of enabled strategies
   */
  async getEnabledStrategyCount(): Promise<number> {
    const strategies = await this.getAllStrategies();
    return strategies.filter(s => s.enabled).length;
  }

  // ===========================================================================
  // Performance Chart Methods
  // ===========================================================================

  /**
   * Get the chart canvas element
   */
  getPerformanceChart(): Locator {
    return this.performanceChart;
  }

  /**
   * Change the chart period
   */
  async setChartPeriod(period: '1h' | '6h' | '24h'): Promise<void> {
    await this.chartPeriodSelect.selectOption(period);
    await this.page.waitForTimeout(500);
  }

  /**
   * Get the selected chart period
   */
  async getChartPeriod(): Promise<string> {
    return await this.chartPeriodSelect.inputValue();
  }

  // ===========================================================================
  // Trades Table Methods
  // ===========================================================================

  /**
   * Get all trades from the table
   */
  async getTrades(): Promise<Array<{ time: string; strategy: string; market: string; profit: string; status: string }>> {
    const rows = this.tradesTableBody.locator('tr:not([colspan])');
    const count = await rows.count();
    const trades: Array<{ time: string; strategy: string; market: string; profit: string; status: string }> = [];

    for (let i = 0; i < count; i++) {
      const row = rows.nth(i);
      const cells = row.locator('td');
      trades.push({
        time: await cells.nth(0).textContent() || '',
        strategy: await cells.nth(1).textContent() || '',
        market: await cells.nth(2).textContent() || '',
        profit: await cells.nth(3).textContent() || '',
        status: await cells.nth(4).textContent() || ''
      });
    }

    return trades;
  }

  /**
   * Get the count of trades in the table
   */
  async getTradesCount(): Promise<number> {
    const rows = this.tradesTableBody.locator('tr:not([colspan])');
    return await rows.count();
  }

  // ===========================================================================
  // System Status Methods
  // ===========================================================================

  /**
   * Get the current run mode
   */
  async getRunMode(): Promise<string> {
    return await this.runModeBadge.textContent() || '';
  }

  /**
   * Get subscribed markets count
   */
  async getSubscribedMarkets(): Promise<string> {
    return await this.subscribedMarkets.textContent() || '';
  }

  /**
   * Get opportunities detected count
   */
  async getOpportunitiesDetected(): Promise<string> {
    return await this.totalOpportunities.textContent() || '';
  }

  /**
   * Get trades executed count
   */
  async getTradesExecuted(): Promise<string> {
    return await this.totalTrades.textContent() || '';
  }

  // ===========================================================================
  // Logs Methods
  // ===========================================================================

  /**
   * Get all log entries
   */
  async getLogs(): Promise<string[]> {
    const logEntries = this.logsContainer.locator('.log-entry');
    const count = await logEntries.count();
    const logs: string[] = [];

    for (let i = 0; i < count; i++) {
      logs.push(await logEntries.nth(i).textContent() || '');
    }

    return logs;
  }

  /**
   * Get the count of log entries
   */
  async getLogsCount(): Promise<number> {
    const logEntries = this.logsContainer.locator('.log-entry');
    return await logEntries.count();
  }

  // ===========================================================================
  // Toast Notification Methods
  // ===========================================================================

  /**
   * Wait for a toast notification to appear
   */
  async waitForToast(message?: string, timeout = 5000): Promise<Locator> {
    const toast = this.page.locator('.fixed.top-20.right-4').filter({ hasText: message || '' });
    await toast.waitFor({ state: 'visible', timeout });
    return toast;
  }

  /**
   * Check if a toast with specific message exists
   */
  async hasToast(message: string): Promise<boolean> {
    try {
      const toast = await this.waitForToast(message, 2000);
      return await toast.isVisible();
    } catch {
      return false;
    }
  }

  /**
   * Get all current toast notifications
   */
  async getToasts(): Promise<Locator[]> {
    const toasts = await this.page.locator('.fixed.top-20.right-4').all();
    return toasts;
  }

  // ===========================================================================
  // Refresh Methods
  // ===========================================================================

  /**
   * Click the refresh button
   */
  async refresh(): Promise<void> {
    await this.refreshButton.click();
    await this.page.waitForTimeout(1000);
  }

  /**
   * Wait for the next auto-refresh cycle
   */
  async waitForAutoRefresh(): Promise<void> {
    // Wait for 2 seconds (the refresh interval) plus a bit more
    await this.page.waitForTimeout(2500);
  }

  // ===========================================================================
  // Verification Methods
  // ===========================================================================

  /**
   * Verify dashboard title is correct
   */
  async verifyTitle(): Promise<boolean> {
    const title = await this.page.title();
    return title.includes('PolyArb-X Dashboard');
  }

  /**
   * Verify all metric cards are visible
   */
  async verifyMetricCardsVisible(): Promise<boolean> {
    const cards = [
      this.accountBalanceCard,
      this.positionValueCard,
      this.totalProfitCard,
      this.totalAssetsCard
    ];

    for (const card of cards) {
      if (!await card.isVisible()) {
        return false;
      }
    }

    return true;
  }

  /**
   * Take a screenshot
   */
  async screenshot(path: string, fullPage = false): Promise<void> {
    await this.page.screenshot({ path, fullPage });
  }
}
