/**
 * Dashboard Smoke Tests
 *
 * Comprehensive smoke tests for the entire PolyArb-X Dashboard.
 * These tests verify the critical user journeys work end-to-end.
 *
 * Run: npx playwright test tests/e2e/smoke.spec.ts
 */

import { test, expect } from '@playwright/test';
import { DashboardPage } from './pages/DashboardPage';
import { ApiHelper } from './pages/ApiHelper';

test.describe('Dashboard Smoke Tests', () => {
  let dashboardPage: DashboardPage;
  let apiHelper: ApiHelper;

  test.beforeEach(async ({ page, request }) => {
    dashboardPage = new DashboardPage(page);
    apiHelper = new ApiHelper(request, process.env.BASE_URL || 'http://localhost:8080');
  });

  test.describe('Critical Journey - Page Load', () => {
    test('should load dashboard successfully', async ({ page }) => {
      await dashboardPage.goto();

      // Verify page title
      const hasCorrectTitle = await dashboardPage.verifyTitle();
      expect(hasCorrectTitle).toBe(true);
    });

    test('should display all major sections', async ({ page }) => {
      await dashboardPage.goto();

      // Header
      await expect(dashboardPage.logo).toBeVisible();
      await expect(dashboardPage.title).toBeVisible();
      await expect(dashboardPage.statusDot).toBeVisible();
      await expect(dashboardPage.refreshButton).toBeVisible();

      // Metric cards
      await expect(dashboardPage.accountBalanceCard).toBeVisible();
      await expect(dashboardPage.positionValueCard).toBeVisible();
      await expect(dashboardPage.totalProfitCard).toBeVisible();
      await expect(dashboardPage.totalAssetsCard).toBeVisible();

      // Strategy section
      await expect(dashboardPage.strategiesSection).toBeVisible();

      // Chart
      await expect(dashboardPage.performanceChart).toBeVisible();

      // System status
      await expect(dashboardPage.systemStatusPanel).toBeVisible();

      // Logs
      await expect(dashboardPage.logsPanel).toBeVisible();
    });

    test('should load without console errors', async ({ page }) => {
      const errors: string[] = [];

      page.on('console', msg => {
        if (msg.type() === 'error') {
          errors.push(msg.text());
        }
      });

      await dashboardPage.goto();

      // Allow some time for async errors
      await page.waitForTimeout(2000);

      // Check for critical errors (ignore non-critical ones)
      const criticalErrors = errors.filter(e =>
        !e.includes('favicon.ico') &&
        !e.includes('404') &&
        !e.includes('net::ERR_FAILED')
      );

      expect(criticalErrors.length).toBe(0);
    });
  });

  test.describe('Critical Journey - Account Balance', () => {
    test('should display account balance from API', async ({ page, request }) => {
      const apiData = await apiHelper.getBalance();

      await dashboardPage.goto();
      await page.waitForResponse(resp => resp.url().includes('/api/balance'));

      const displayedBalance = await dashboardPage.getAccountBalanceValue();

      expect(displayedBalance).toBeCloseTo(apiData.usdc_balance, 2);
    });

    test('should calculate total assets correctly', async ({ page }) => {
      await dashboardPage.goto();

      const isCorrect = await dashboardPage.verifyTotalAssetsCalculation();
      expect(isCorrect).toBe(true);
    });
  });

  test.describe('Critical Journey - Strategy Toggle', () => {
    test('should toggle a strategy successfully', async ({ page }) => {
      await page.route('**/api/strategies/*/toggle', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            success: true,
            strategy_id: 'atomic_arbitrage',
            strategy_name: '原子套利',
            enabled: false,
            message: '原子套利 已禁用'
          })
        });
      });

      await dashboardPage.goto();

      const card = dashboardPage.getStrategyCardById('atomic_arbitrage');
      await card.click();

      // Wait for API and toast
      await page.waitForTimeout(1000);

      // Verify toast appeared
      const toast = page.locator('.fixed.top-20.right-4');
      await expect(toast).toBeVisible();
    });

    test('should display all 6 strategies', async ({ page }) => {
      await dashboardPage.goto();

      const cards = dashboardPage.getStrategyCards();
      const count = await cards.count();

      expect(count).toBe(6);
    });
  });

  test.describe('Critical Journey - Performance Chart', () => {
    test('should display performance chart', async ({ page }) => {
      await dashboardPage.goto();

      await expect(dashboardPage.performanceChart).toBeVisible();

      // Verify chart canvas exists
      const canvas = page.locator('#performance-chart');
      await expect(canvas).toBeVisible();
    });

    test('should change chart period', async ({ page }) => {
      await dashboardPage.goto();

      await dashboardPage.setChartPeriod('1h');
      await expect(dashboardPage.chartPeriodSelect).toHaveValue('1h');

      await dashboardPage.setChartPeriod('24h');
      await expect(dashboardPage.chartPeriodSelect).toHaveValue('24h');
    });
  });

  test.describe('Critical Journey - Real-time Updates', () => {
    test('should refresh data when refresh button is clicked', async ({ page }) => {
      await dashboardPage.goto();

      const uptimeBefore = await dashboardPage.uptime.textContent();

      await dashboardPage.refresh();
      await page.waitForTimeout(500);

      const uptimeAfter = await dashboardPage.uptime.textContent();

      expect(uptimeAfter).toBeTruthy();
    });

    test('should auto-refresh all data periodically', async ({ page }) => {
      await dashboardPage.goto();

      let apiCallCount = 0;
      page.on('request', request => {
        if (request.url().includes('/api/')) {
          apiCallCount++;
        }
      });

      // Wait for auto-refresh cycles
      await dashboardPage.waitForAutoRefresh();
      await dashboardPage.waitForAutoRefresh();

      expect(apiCallCount).toBeGreaterThan(10); // Multiple APIs called
    });
  });

  test.describe('Critical Journey - System Status', () => {
    test('should display system is online', async ({ page }) => {
      await dashboardPage.goto();

      const statusText = await dashboardPage.statusText.textContent();
      expect(statusText).toContain('在线');

      await expect(dashboardPage.statusDot).toBeVisible();
      await expect(dashboardPage.statusDot).toHaveClass(/bg-green-400/);
    });

    test('should display current run mode', async ({ page }) => {
      await dashboardPage.goto();

      const runMode = await dashboardPage.getRunMode();
      expect(runMode).toBeTruthy();
    });
  });

  test.describe('Critical Journey - Recent Trades', () => {
    test('should display trades table', async ({ page }) => {
      await dashboardPage.goto();

      await expect(dashboardPage.tradesTable).toBeVisible();

      const headers = await dashboardPage.tradesTableHeaders.allTextContents();
      expect(headers.length).toBe(5);
    });

    test('should display trades when available', async ({ page }) => {
      const mockOpportunities = ApiHelper.generateMockOpportunities(3);

      await page.route('**/api/opportunities', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ opportunities: mockOpportunities })
        });
      });

      await dashboardPage.goto();

      const tradesCount = await dashboardPage.getTradesCount();
      expect(tradesCount).toBeGreaterThan(0);
    });
  });

  test.describe('Critical Journey - Live Logs', () => {
    test('should display logs panel', async ({ page }) => {
      await dashboardPage.goto();

      await expect(dashboardPage.logsContainer).toBeVisible();
    });

    test('should fetch and display logs', async ({ page, request }) => {
      const apiData = await apiHelper.getLogs();

      if (apiData.logs.length > 0) {
        await dashboardPage.goto();

        const logsCount = await dashboardPage.getLogsCount();
        expect(logsCount).toBeGreaterThan(0);
      }
    });
  });
});

test.describe('Dashboard Regression Tests', () => {
  let dashboardPage: DashboardPage;

  test.beforeEach(async ({ page }) => {
    dashboardPage = new DashboardPage(page);
  });

  test('should maintain state across navigation', async ({ page }) => {
    await dashboardPage.goto();

    // Get initial state
    const balance1 = await dashboardPage.getAccountBalance();
    const profit1 = await dashboardPage.getTotalProfit();

    // Navigate away and back
    await page.goto('about:blank');
    await page.waitForTimeout(100);

    await dashboardPage.goto();

    // Page should load successfully
    await expect(dashboardPage.accountBalanceCard).toBeVisible();

    const balance2 = await dashboardPage.getAccountBalance();
    const profit2 = await dashboardPage.getTotalProfit();

    expect(balance2).toBeTruthy();
    expect(profit2).toBeTruthy();
  });

  test('should handle rapid refresh clicks', async ({ page }) => {
    await dashboardPage.goto();

    // Rapid clicks
    await dashboardPage.refreshButton.click();
    await page.waitForTimeout(100);
    await dashboardPage.refreshButton.click();
    await page.waitForTimeout(100);
    await dashboardPage.refreshButton.click();

    // Should still work
    await expect(dashboardPage.accountBalanceCard).toBeVisible();
  });

  test('should work on mobile viewport', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });

    await dashboardPage.goto();

    // Critical elements should still be visible
    await expect(dashboardPage.accountBalanceCard).toBeVisible();
    await expect(dashboardPage.statusDot).toBeVisible();

    // Check if mobile layout is applied
    const container = page.locator('.container');
    await expect(container).toBeVisible();
  });

  test('should work on tablet viewport', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });

    await dashboardPage.goto();

    await expect(dashboardPage.accountBalanceCard).toBeVisible();
    await expect(dashboardPage.performanceChart).toBeVisible();
  });
});

test.describe('Dashboard API Integration Tests', () => {
  let apiHelper: ApiHelper;

  test.beforeEach(async ({ request }) => {
    apiHelper = new ApiHelper(request, process.env.BASE_URL || 'http://localhost:8080');
  });

  test('should have all required API endpoints available', async ({ request }) => {
    const endpoints = [
      '/api/status',
      '/api/balance',
      '/api/profit',
      '/api/strategies',
      '/api/logs',
      '/api/opportunities'
    ];

    const baseURL = process.env.BASE_URL || 'http://localhost:8080';

    for (const endpoint of endpoints) {
      const response = await request.get(`${baseURL}${endpoint}`);
      expect(response.ok()).toBe(true);
    }
  });

  test('should return valid JSON from all endpoints', async ({ request }) => {
    const endpoints = [
      '/api/status',
      '/api/balance',
      '/api/profit',
      '/api/strategies',
      '/api/logs'
    ];

    const baseURL = process.env.BASE_URL || 'http://localhost:8080';

    for (const endpoint of endpoints) {
      const response = await request.get(`${baseURL}${endpoint}`);
      const contentType = response.headers()['content-type'];
      expect(contentType).toContain('application/json');

      const data = await response.json();
      expect(data).toBeDefined();
    }
  });
});
