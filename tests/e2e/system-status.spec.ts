/**
 * System Status Panel E2E Tests
 *
 * Tests for the system status panel showing:
 * - Run mode (Dry-Run/Live)
 * - Subscribed markets
 * - Orderbook updates
 * - Circuit breaker trips
 * - Anomaly detections
 * API: GET /api/status
 */

import { test, expect } from '@playwright/test';
import { DashboardPage } from './pages/DashboardPage';
import { ApiHelper } from './pages/ApiHelper';

test.describe('System Status Panel', () => {
  let dashboardPage: DashboardPage;
  let apiHelper: ApiHelper;

  test.beforeEach(async ({ page, request }) => {
    dashboardPage = new DashboardPage(page);
    apiHelper = new ApiHelper(request, process.env.BASE_URL || 'http://localhost:8080');
  });

  test.describe('Page Load - Status Panel', () => {
    test('should display system status panel', async ({ page }) => {
      await dashboardPage.goto();

      await expect(dashboardPage.systemStatusPanel).toBeVisible();
    });

    test('should display system status title', async ({ page }) => {
      await dashboardPage.goto();

      await expect(dashboardPage.systemStatusPanel).toContainText('系统状态');
    });
  });

  test.describe('Status Metrics Display', () => {
    test('should display run mode badge', async ({ page }) => {
      await dashboardPage.goto();

      await expect(dashboardPage.runModeBadge).toBeVisible();
    });

    test('should display run mode as Dry-Run by default', async ({ page }) => {
      await dashboardPage.goto();

      const mode = await dashboardPage.getRunMode();
      expect(mode.toLowerCase()).toContain('dry');
    });

    test('should display subscribed markets count', async ({ page }) => {
      await dashboardPage.goto();

      await expect(dashboardPage.subscribedMarkets).toBeVisible();

      const count = await dashboardPage.getSubscribedMarkets();
      expect(count).toBeTruthy();
    });

    test('should display all status metrics', async ({ page }) => {
      await dashboardPage.goto();

      await expect(dashboardPage.subscribedMarkets).toBeVisible();
      await expect(dashboardPage.orderbookUpdates).toBeVisible();
      await expect(dashboardPage.circuitTrips).toBeVisible();
      await expect(dashboardPage.anomalyDetections).toBeVisible();
    });
  });

  test.describe('API Integration - Status', () => {
    test('should fetch status from API on page load', async ({ page }) => {
      const statusRequests: string[] = [];
      page.on('request', request => {
        if (request.url().includes('/api/status')) {
          statusRequests.push(request.url());
        }
      });

      await dashboardPage.goto();

      expect(statusRequests.length).toBeGreaterThan(0);
    });

    test('should display data from API response', async ({ page, request }) => {
      const apiData = await apiHelper.getStatus();

      await dashboardPage.goto();

      const opportunities = await dashboardPage.getOpportunitiesDetected();
      const trades = await dashboardPage.getTradesExecuted();

      expect(opportunities).toBeTruthy();
      expect(trades).toBeTruthy();
    });

    test('should update status metrics on refresh', async ({ page }) => {
      await dashboardPage.goto();

      const opportunitiesBefore = await dashboardPage.getOpportunitiesDetected();

      // Mock different status
      await page.route('**/api/status', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            status: '在线',
            mode: 'dry-run',
            uptime: '1h 0m 0s',
            subscribed_markets: 10,
            opportunities_detected: 999,
            trades_executed: 50
          })
        });
      });

      await dashboardPage.refresh();
      await page.waitForTimeout(500);

      const opportunitiesAfter = await dashboardPage.getOpportunitiesDetected();
      expect(opportunitiesAfter).toContain('999');
    });
  });

  test.describe('Status Badge Styling', () => {
    test('should display run mode with appropriate styling', async ({ page }) => {
      await dashboardPage.goto();

      const badgeClass = await dashboardPage.runModeBadge.getAttribute('class') || '';

      // Should have blue styling for Dry-Run
      expect(badgeClass).toContain('bg-blue-500');
    });

    test('should display circuit trips with warning color when non-zero', async ({ page }) => {
      await page.route('**/api/status', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            status: '在线',
            mode: 'dry-run',
            uptime: '0h 0m 0s',
            subscribed_markets: 2,
            opportunities_detected: 0,
            trades_executed: 0
          })
        });
      });

      await dashboardPage.goto();

      const tripsClass = await dashboardPage.circuitTrips.getAttribute('class') || '';
      expect(tripsClass).toContain('text-yellow-400');
    });

    test('should display anomaly detections with error color when non-zero', async ({ page }) => {
      await dashboardPage.goto();

      const detectionsClass = await dashboardPage.anomalyDetections.getAttribute('class') || '';
      expect(detectionsClass).toContain('text-red-400');
    });
  });

  test.describe('Real-time Updates', () => {
    test('should auto-refresh status periodically', async ({ page }) => {
      await dashboardPage.goto();

      let apiCallCount = 0;
      page.on('request', request => {
        if (request.url().includes('/api/status')) {
          apiCallCount++;
        }
      });

      await dashboardPage.waitForAutoRefresh();
      await dashboardPage.waitForAutoRefresh();

      expect(apiCallCount).toBeGreaterThan(1);
    });

    test('should update uptime counter', async ({ page }) => {
      await dashboardPage.goto();

      const uptime1 = await dashboardPage.uptime.textContent();

      await page.waitForTimeout(2000);

      const uptime2 = await dashboardPage.uptime.textContent();

      expect(uptime2).not.toBe(uptime1);
    });
  });

  test.describe('Header Status', () => {
    test('should display online status in header', async ({ page }) => {
      await dashboardPage.goto();

      await expect(dashboardPage.statusDot).toBeVisible();
      await expect(dashboardPage.statusText).toBeVisible();
    });

    test('should display pulsing status dot', async ({ page }) => {
      await dashboardPage.goto();

      const dotClass = await dashboardPage.statusDot.getAttribute('class') || '';

      expect(dotClass).toContain('pulse-dot');
      expect(dotClass).toContain('bg-green-400');
    });

    test('should display uptime in header', async ({ page }) => {
      await dashboardPage.goto();

      const uptime = await dashboardPage.uptime.textContent();

      expect(uptime).toMatch(/\d+h\s+\d+m\s+\d+s/);
    });
  });

  test.describe('Edge Cases', () => {
    test('should handle zero values gracefully', async ({ page }) => {
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
            trades_executed: 0
          })
        });
      });

      await dashboardPage.goto();

      const opportunities = await dashboardPage.getOpportunitiesDetected();
      const trades = await dashboardPage.getTradesExecuted();

      expect(opportunities).toContain('0');
      expect(trades).toContain('0');
    });

    test('should handle API errors gracefully', async ({ page }) => {
      await page.route('**/api/status', async route => {
        await route.abort('failed');
      });

      await dashboardPage.goto();

      // Panel should still be visible
      await expect(dashboardPage.systemStatusPanel).toBeVisible();
    });
  });
});
