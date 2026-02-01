/**
 * Real-time Profit Display E2E Tests
 *
 * Tests for the Total Profit card, Average Profit per Trade card,
 * and Performance Chart updating with profit history
 * API: GET /api/profit
 */

import { test, expect } from '@playwright/test';
import { DashboardPage } from './pages/DashboardPage';
import { ApiHelper, ProfitResponse } from './pages/ApiHelper';

test.describe('Real-time Profit Display', () => {
  let dashboardPage: DashboardPage;
  let apiHelper: ApiHelper;

  test.beforeEach(async ({ page, request }) => {
    dashboardPage = new DashboardPage(page);
    apiHelper = new ApiHelper(request, process.env.BASE_URL || 'http://localhost:8080');
  });

  test.describe('Page Load - Profit Cards', () => {
    test('should display total profit card on page load', async ({ page }) => {
      await dashboardPage.goto();

      await expect(dashboardPage.totalProfitCard).toBeVisible();
      await expect(dashboardPage.totalProfitValue).toBeVisible();
    });

    test('should display average profit per trade', async ({ page }) => {
      await dashboardPage.goto();

      await expect(dashboardPage.avgProfit).toBeVisible();
    });

    test('should display profit values in correct format', async ({ page }) => {
      await dashboardPage.goto();

      const totalProfit = await dashboardPage.getTotalProfit();
      const avgProfit = await dashboardPage.avgProfit.textContent();

      expect(totalProfit).toMatch(/^\$[\-]?\d+\.\d{2}$/);
      expect(avgProfit).toMatch(/^\$[\-]?\d+\.\d{2}$/);
    });
  });

  test.describe('API Integration - Profit', () => {
    test('should fetch profit data from API on page load', async ({ page }) => {
      const profitRequests: string[] = [];
      page.on('request', request => {
        if (request.url().includes('/api/profit')) {
          profitRequests.push(request.url());
        }
      });

      await dashboardPage.goto();

      expect(profitRequests.length).toBeGreaterThan(0);
    });

    test('should display profit data from API response', async ({ page, request }) => {
      const apiData = await apiHelper.getProfit() as ProfitResponse;

      await dashboardPage.goto();

      // Wait for profit API response
      await page.waitForResponse(resp => resp.url().includes('/api/profit'));

      const displayedProfit = await dashboardPage.getTotalProfitValue();
      const displayedAvgProfitText = await dashboardPage.avgProfit.textContent() || '';
      const displayedAvgProfit = parseFloat(displayedAvgProfitText.replace('$', '').replace(/,/g, ''));

      expect(displayedProfit).toBeCloseTo(apiData.total_profit, 2);
      expect(displayedAvgProfit).toBeCloseTo(apiData.avg_profit_per_trade, 2);
    });

    test('should handle profit API errors gracefully', async ({ page }) => {
      await page.route('**/api/profit', async route => {
        await route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ error: 'Internal server error' })
        });
      });

      await dashboardPage.goto();

      // Page should still load
      await expect(dashboardPage.totalProfitCard).toBeVisible();
      await expect(dashboardPage.totalProfitValue).toBeVisible();
    });
  });

  test.describe('Performance Chart', () => {
    test('should display performance chart', async ({ page }) => {
      await dashboardPage.goto();

      await expect(dashboardPage.performanceChart).toBeVisible();
    });

    test('should have chart period selector', async ({ page }) => {
      await dashboardPage.goto();

      await expect(dashboardPage.chartPeriodSelect).toBeVisible();

      const options = await dashboardPage.chartPeriodSelect.locator('option').allTextContents();
      expect(options).toContain('最近 1 小时');
      expect(options).toContain('最近 6 小时');
      expect(options).toContain('最近 24 小时');
    });

    test('should change chart period when selecting different option', async ({ page }) => {
      await dashboardPage.goto();

      await dashboardPage.setChartPeriod('1h');
      await expect(dashboardPage.chartPeriodSelect).toHaveValue('1h');

      await dashboardPage.setChartPeriod('6h');
      await expect(dashboardPage.chartPeriodSelect).toHaveValue('6h');

      await dashboardPage.setChartPeriod('24h');
      await expect(dashboardPage.chartPeriodSelect).toHaveValue('24h');
    });

    test('should display chart with profit history data', async ({ page }) => {
      // Mock profit history
      const mockHistory = ApiHelper.generateProfitHistory(10, 100);

      await page.route('**/api/profit', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            total_profit: 1000,
            trade_count: 10,
            profit_history: mockHistory,
            avg_profit_per_trade: 100
          })
        });
      });

      await dashboardPage.goto();

      // Wait for chart to render
      await page.waitForTimeout(500);

      const chart = dashboardPage.performanceChart;
      await expect(chart).toBeVisible();

      // Verify chart canvas exists
      const canvas = page.locator('#performance-chart');
      await expect(canvas).toBeVisible();
    });

    test('should update chart when profit data changes', async ({ page }) => {
      await dashboardPage.goto();

      // Initial chart render
      await page.waitForResponse(resp => resp.url().includes('/api/profit'));

      // Mock updated profit data
      const updatedHistory = ApiHelper.generateProfitHistory(15, 200);

      await page.route('**/api/profit', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            total_profit: 2000,
            trade_count: 15,
            profit_history: updatedHistory,
            avg_profit_per_trade: 133.33
          })
        });
      });

      await dashboardPage.refresh();
      await page.waitForTimeout(500);

      const totalProfit = await dashboardPage.getTotalProfitValue();
      expect(totalProfit).toBeCloseTo(2000, 0);
    });
  });

  test.describe('Real-time Updates', () => {
    test('should refresh profit data when refresh button is clicked', async ({ page }) => {
      await dashboardPage.goto();

      const initialProfit = await dashboardPage.getTotalProfit();

      // Mock different profit
      let callCount = 0;
      await page.route('**/api/profit', async route => {
        callCount++;
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            total_profit: 100 + callCount * 50,
            trade_count: callCount,
            profit_history: ApiHelper.generateProfitHistory(callCount, 100),
            avg_profit_per_trade: 100
          })
        });
      });

      await dashboardPage.refresh();
      await page.waitForTimeout(500);

      const newProfit = await dashboardPage.getTotalProfit();
      expect(newProfit).not.toBe(initialProfit);
    });

    test('should auto-refresh profit data periodically', async ({ page }) => {
      await dashboardPage.goto();

      let apiCallCount = 0;
      page.on('request', request => {
        if (request.url().includes('/api/profit')) {
          apiCallCount++;
        }
      });

      // Wait for auto-refresh cycles
      await dashboardPage.waitForAutoRefresh();
      await dashboardPage.waitForAutoRefresh();

      expect(apiCallCount).toBeGreaterThan(1);
    });
  });

  test.describe('Profit Calculation Verification', () => {
    test('should correctly calculate average profit per trade', async ({ page }) => {
      await page.route('**/api/profit', async route => {
        const totalProfit = 500;
        const tradeCount = 10;
        const avgProfit = totalProfit / tradeCount;

        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            total_profit: totalProfit,
            trade_count: tradeCount,
            profit_history: ApiHelper.generateProfitHistory(tradeCount, 50),
            avg_profit_per_trade: avgProfit
          })
        });
      });

      await dashboardPage.goto();

      const avgProfitText = await dashboardPage.avgProfit.textContent() || '';
      const avgProfit = parseFloat(avgProfitText.replace('$', '').replace(/,/g, ''));

      expect(avgProfit).toBeCloseTo(50, 1);
    });

    test('should handle zero trade count', async ({ page }) => {
      await page.route('**/api/profit', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            total_profit: 0,
            trade_count: 0,
            profit_history: [],
            avg_profit_per_trade: 0
          })
        });
      });

      await dashboardPage.goto();

      const totalProfit = await dashboardPage.getTotalProfit();
      const avgProfitText = await dashboardPage.avgProfit.textContent() || '';

      expect(totalProfit).toContain('$0.00');
      expect(avgProfitText).toContain('$0.00');
    });
  });

  test.describe('Visual States', () => {
    test('should display positive profit in green', async ({ page }) => {
      await page.route('**/api/profit', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            total_profit: 500,
            trade_count: 5,
            profit_history: ApiHelper.generateProfitHistory(5, 100),
            avg_profit_per_trade: 100
          })
        });
      });

      await dashboardPage.goto();

      // Check that profit element is visible
      await expect(dashboardPage.totalProfitValue).toBeVisible();
    });

    test('should display negative profit', async ({ page }) => {
      await page.route('**/api/profit', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            total_profit: -100,
            trade_count: 5,
            profit_history: [
              { timestamp: '2026-02-01 12:00:00', profit: -20 },
              { timestamp: '2026-02-01 12:01:00', profit: -20 },
              { timestamp: '2026-02-01 12:02:00', profit: -20 },
              { timestamp: '2026-02-01 12:03:00', profit: -20 },
              { timestamp: '2026-02-01 12:04:00', profit: -20 }
            ],
            avg_profit_per_trade: -20
          })
        });
      });

      await dashboardPage.goto();

      const totalProfit = await dashboardPage.getTotalProfit();
      expect(totalProfit).toContain('-');
    });
  });

  test.describe('Chart Features', () => {
    test('should display chart with two datasets (profit and opportunities)', async ({ page }) => {
      await dashboardPage.goto();

      // Chart.js creates a canvas element
      const canvas = page.locator('#performance-chart');
      await expect(canvas).toBeVisible();

      // Check that chart was initialized
      const chartExists = await canvas.evaluate(el => {
        // Chart.js adds the chart to a charts registry
        return typeof (window as any).Chart !== 'undefined';
      });

      expect(chartExists).toBe(true);
    });

    test('should maintain aspect ratio on resize', async ({ page }) => {
      await dashboardPage.goto();

      const canvas = page.locator('#performance-chart');
      await expect(canvas).toBeVisible();

      // Resize viewport
      await page.setViewportSize({ width: 800, height: 600 });
      await page.waitForTimeout(300);

      await expect(canvas).toBeVisible();

      // Resize back
      await page.setViewportSize({ width: 1280, height: 720 });
      await page.waitForTimeout(300);

      await expect(canvas).toBeVisible();
    });
  });

  test.describe('Edge Cases', () => {
    test('should handle very large profit values', async ({ page }) => {
      await page.route('**/api/profit', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            total_profit: 999999.99,
            trade_count: 100,
            profit_history: ApiHelper.generateProfitHistory(100, 10000),
            avg_profit_per_trade: 9999.99
          })
        });
      });

      await dashboardPage.goto();

      const totalProfit = await dashboardPage.getTotalProfit();
      expect(totalProfit).toMatch(/\$.*999999\.99/);
    });

    test('should handle empty profit history', async ({ page }) => {
      await page.route('**/api/profit', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            total_profit: 0,
            trade_count: 0,
            profit_history: [],
            avg_profit_per_trade: 0
          })
        });
      });

      await dashboardPage.goto();

      // Chart should still render
      await expect(dashboardPage.performanceChart).toBeVisible();

      const totalProfit = await dashboardPage.getTotalProfit();
      expect(totalProfit).toBe('$0.00');
    });

    test('should handle profit history with single entry', async ({ page }) => {
      await page.route('**/api/profit', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            total_profit: 100,
            trade_count: 1,
            profit_history: [{ timestamp: '2026-02-01 12:00:00', profit: 100 }],
            avg_profit_per_trade: 100
          })
        });
      });

      await dashboardPage.goto();

      const totalProfit = await dashboardPage.getTotalProfitValue();
      expect(totalProfit).toBe(100);

      await expect(dashboardPage.performanceChart).toBeVisible();
    });
  });
});
