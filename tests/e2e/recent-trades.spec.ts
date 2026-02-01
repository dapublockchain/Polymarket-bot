/**
 * Recent Trades Table E2E Tests
 *
 * Tests for the recent trades table showing:
 * - Time
 * - Strategy
 * - Market
 * - Profit
 * - Status
 */

import { test, expect } from '@playwright/test';
import { DashboardPage } from './pages/DashboardPage';
import { ApiHelper } from './pages/ApiHelper';

test.describe('Recent Trades Table', () => {
  let dashboardPage: DashboardPage;
  let apiHelper: ApiHelper;

  test.beforeEach(async ({ page, request }) => {
    dashboardPage = new DashboardPage(page);
    apiHelper = new ApiHelper(request, process.env.BASE_URL || 'http://localhost:8080');
  });

  test.describe('Page Load - Trades Table', () => {
    test('should display trades table section', async ({ page }) => {
      await dashboardPage.goto();

      await expect(dashboardPage.tradesTable).toBeVisible();
    });

    test('should display trades table with title', async ({ page }) => {
      await dashboardPage.goto();

      const tableSection = page.locator('.glass-card').filter({ hasText: '最近交易' });
      await expect(tableSection).toBeVisible();
    });

    test('should display table headers', async ({ page }) => {
      await dashboardPage.goto();

      const headers = await dashboardPage.tradesTableHeaders.allTextContents();

      expect(headers).toContain('时间');
      expect(headers).toContain('策略');
      expect(headers).toContain('市场');
      expect(headers).toContain('利润');
      expect(headers).toContain('状态');
    });
  });

  test.describe('Empty State', () => {
    test('should display empty state when no trades', async ({ page }) => {
      await page.route('**/api/opportunities', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ opportunities: [] })
        });
      });

      await dashboardPage.goto();

      const tradesCount = await dashboardPage.getTradesCount();
      expect(tradesCount).toBe(0);
    });

    test('should display empty message in table when no trades', async ({ page }) => {
      await page.route('**/api/opportunities', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ opportunities: [] })
        });
      });

      await dashboardPage.goto();

      const tbody = dashboardPage.tradesTableBody;
      await expect(tbody).toContainText('暂无交易记录');
    });
  });

  test.describe('Trades Display', () => {
    test('should display trades from API', async ({ page }) => {
      const mockOpportunities = ApiHelper.generateMockOpportunities(5);

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

    test('should display trade data correctly', async ({ page }) => {
      const mockOpportunities = [
        {
          id: 1,
          timestamp: '12:30:45',
          pair: 'Trump vs Harris',
          yes_price: 0.45,
          no_price: 0.52,
          profit: 3.5,
          status: '已执行'
        }
      ];

      await page.route('**/api/opportunities', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ opportunities: mockOpportunities })
        });
      });

      await dashboardPage.goto();

      const trades = await dashboardPage.getTrades();
      expect(trades.length).toBeGreaterThan(0);

      const firstTrade = trades[0];
      expect(firstTrade.pair).toBeTruthy();
      expect(firstTrade.profit).toBeTruthy();
      expect(firstTrade.status).toBeTruthy();
    });

    test('should color code profit values', async ({ page }) => {
      const mockOpportunities = [
        {
          id: 1,
          timestamp: '12:30:45',
          pair: 'Profit Trade',
          yes_price: 0.45,
          no_price: 0.52,
          profit: 5.0,
          status: '已执行'
        },
        {
          id: 2,
          timestamp: '12:31:45',
          pair: 'Loss Trade',
          yes_price: 0.45,
          no_price: 0.52,
          profit: -2.0,
          status: '已执行'
        }
      ];

      await page.route('**/api/opportunities', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ opportunities: mockOpportunities })
        });
      });

      await dashboardPage.goto();

      // Check that positive profit has green color
      const positiveProfitCell = dashboardPage.tradesTableBody.locator('tr').first().locator('td').nth(3);
      const positiveClass = await positiveProfitCell.getAttribute('class') || '';
      expect(positiveClass).toContain('text-green-400');

      // Check that negative profit has red color
      const negativeProfitCell = dashboardPage.tradesTableBody.locator('tr').nth(1).locator('td').nth(3);
      const negativeClass = await negativeProfitCell.getAttribute('class') || '';
      expect(negativeClass).toContain('text-red-400');
    });
  });

  test.describe('Status Badges', () => {
    test('should display status badge for each trade', async ({ page }) => {
      const mockOpportunities = ApiHelper.generateMockOpportunities(3);

      await page.route('**/api/opportunities', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ opportunities: mockOpportunities })
        });
      });

      await dashboardPage.goto();

      const statusBadges = dashboardPage.tradesTableBody.locator('.strategy-badge');
      const count = await statusBadges.count();

      expect(count).toBeGreaterThan(0);
    });

    test('should display different status badge colors', async ({ page }) => {
      const mockOpportunities = [
        {
          id: 1,
          timestamp: '12:30:45',
          pair: 'Trade 1',
          yes_price: 0.45,
          no_price: 0.52,
          profit: 5.0,
          status: '已执行'
        },
        {
          id: 2,
          timestamp: '12:31:45',
          pair: 'Trade 2',
          yes_price: 0.45,
          no_price: 0.52,
          profit: 0.5,
          status: '已忽略 (利润过低)'
        }
      ];

      await page.route('**/api/opportunities', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ opportunities: mockOpportunities })
        });
      });

      await dashboardPage.goto();

      const executedStatus = dashboardPage.tradesTableBody.locator('tr').first().locator('.strategy-badge');
      const executedClass = await executedStatus.getAttribute('class') || '';

      expect(executedClass).toContain('bg-green-500');
    });
  });

  test.describe('Table Limit', () => {
    test('should display only last 50 trades', async ({ page }) => {
      // Generate 60 mock trades
      const mockOpportunities: Array<any> = [];
      for (let i = 0; i < 60; i++) {
        mockOpportunities.push({
          id: i,
          timestamp: `12:${String(i).padStart(2, '0')}:45`,
          pair: `Trade ${i}`,
          yes_price: 0.45,
          no_price: 0.52,
          profit: Math.random() * 10,
          status: '已执行'
        });
      }

      await page.route('**/api/opportunities', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ opportunities: mockOpportunities })
        });
      });

      await dashboardPage.goto();

      const tradesCount = await dashboardPage.getTradesCount();
      expect(tradesCount).toBeLessThanOrEqual(50);
    });
  });

  test.describe('Real-time Updates', () => {
    test('should update trades table on refresh', async ({ page }) => {
      await dashboardPage.goto();

      const countBefore = await dashboardPage.getTradesCount();

      // Add a new trade
      const mockOpportunities = ApiHelper.generateMockOpportunities(3);
      await page.route('**/api/opportunities', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ opportunities: mockOpportunities })
        });
      });

      await dashboardPage.refresh();
      await page.waitForTimeout(500);

      const countAfter = await dashboardPage.getTradesCount();
      expect(countAfter).toBeGreaterThan(0);
    });

    test('should auto-refresh trades table', async ({ page }) => {
      await dashboardPage.goto();

      let apiCallCount = 0;
      page.on('request', request => {
        if (request.url().includes('/api/opportunities')) {
          apiCallCount++;
        }
      });

      await dashboardPage.waitForAutoRefresh();
      await dashboardPage.waitForAutoRefresh();

      expect(apiCallCount).toBeGreaterThan(1);
    });
  });

  test.describe('Table Styling', () => {
    test('should have hover effect on table rows', async ({ page }) => {
      const mockOpportunities = ApiHelper.generateMockOpportunities(3);

      await page.route('**/api/opportunities', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ opportunities: mockOpportunities })
        });
      });

      await dashboardPage.goto();

      const firstRow = dashboardPage.tradesTableBody.locator('tr').first();

      await firstRow.hover();
      await page.waitForTimeout(100);

      // Row should still be visible
      await expect(firstRow).toBeVisible();
    });

    test('should have borders between rows', async ({ page }) => {
      const mockOpportunities = ApiHelper.generateMockOpportunities(3);

      await page.route('**/api/opportunities', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ opportunities: mockOpportunities })
        });
      });

      await dashboardPage.goto();

      const firstRow = dashboardPage.tradesTableBody.locator('tr').first();
      const borderClass = await firstRow.getAttribute('class') || '';

      expect(borderClass).toContain('border-t');
    });
  });

  test.describe('Edge Cases', () => {
    test('should handle trades with very long market names', async ({ page }) => {
      const mockOpportunities = [
        {
          id: 1,
          timestamp: '12:30:45',
          pair: 'This is a very long market name that might break the layout',
          yes_price: 0.45,
          no_price: 0.52,
          profit: 5.0,
          status: '已执行'
        }
      ];

      await page.route('**/api/opportunities', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ opportunities: mockOpportunities })
        });
      });

      await dashboardPage.goto();

      const trades = await dashboardPage.getTrades();
      expect(trades.length).toBeGreaterThan(0);
    });

    test('should handle very small profit values', async ({ page }) => {
      const mockOpportunities = [
        {
          id: 1,
          timestamp: '12:30:45',
          pair: 'Small Profit',
          yes_price: 0.45,
          no_price: 0.52,
          profit: 0.0001,
          status: '已执行'
        }
      ];

      await page.route('**/api/opportunities', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ opportunities: mockOpportunities })
        });
      });

      await dashboardPage.goto();

      const trades = await dashboardPage.getTrades();
      expect(trades[0].profit).toContain('0.0001');
    });
  });
});
