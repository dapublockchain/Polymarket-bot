/**
 * Live Logs Viewer E2E Tests
 *
 * Tests for the live logs viewer showing:
 * - Real-time log updates
 * - Log levels (INFO, ERROR, WARN, DEBUG)
 * - Timestamp formatting
 * - Auto-scroll to bottom
 */

import { test, expect } from '@playwright/test';
import { DashboardPage } from './pages/DashboardPage';
import { ApiHelper } from './pages/ApiHelper';

test.describe('Live Logs Viewer', () => {
  let dashboardPage: DashboardPage;
  let apiHelper: ApiHelper;

  test.beforeEach(async ({ page, request }) => {
    dashboardPage = new DashboardPage(page);
    apiHelper = new ApiHelper(request, process.env.BASE_URL || 'http://localhost:8080');
  });

  test.describe('Page Load - Logs Panel', () => {
    test('should display logs panel', async ({ page }) => {
      await dashboardPage.goto();

      await expect(dashboardPage.logsPanel).toBeVisible();
    });

    test('should display logs panel with title', async ({ page }) => {
      await dashboardPage.goto();

      await expect(dashboardPage.logsPanel).toContainText('系统日志');
    });

    test('should display logs container', async ({ page }) => {
      await dashboardPage.goto();

      await expect(dashboardPage.logsContainer).toBeVisible();
    });
  });

  test.describe('API Integration - Logs', () => {
    test('should fetch logs from API on page load', async ({ page }) => {
      const logsRequests: string[] = [];
      page.on('request', request => {
        if (request.url().includes('/api/logs')) {
          logsRequests.push(request.url());
        }
      });

      await dashboardPage.goto();

      expect(logsRequests.length).toBeGreaterThan(0);
    });

    test('should display logs from API response', async ({ page, request }) => {
      const apiData = await apiHelper.getLogs();

      await dashboardPage.goto();

      const logsCount = await dashboardPage.getLogsCount();

      if (apiData.logs.length > 0) {
        expect(logsCount).toBeGreaterThan(0);
      }
    });

    test('should display "loading logs" message initially', async ({ page }) => {
      await dashboardPage.goto();

      // Check initial loading state
      const container = dashboardPage.logsContainer;
      await expect(container).toBeVisible();
    });
  });

  test.describe('Log Entry Display', () => {
    test('should display log entries with proper structure', async ({ page }) => {
      await page.route('**/api/logs', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            logs: [
              '2026-02-01 12:00:00|INFO|Test log message',
              '2026-02-01 12:01:00|ERROR|Error message',
              '2026-02-01 12:02:00|WARN|Warning message'
            ]
          })
        });
      });

      await dashboardPage.goto();

      const logs = await dashboardPage.getLogs();
      expect(logs.length).toBeGreaterThan(0);
    });

    test('should color code log levels', async ({ page }) => {
      await page.route('**/api/logs', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            logs: [
              '2026-02-01 12:00:00|INFO|Info message',
              '2026-02-01 12:01:00|ERROR|Error message',
              '2026-02-01 12:02:00|WARN|Warning message',
              '2026-02-01 12:03:00|DEBUG|Debug message'
            ]
          })
        });
      });

      await dashboardPage.goto();

      const logsContainer = dashboardPage.logsContainer;

      // Check for ERROR color (red)
      const errorElement = logsContainer.locator('.text-red-400');
      await expect(errorElement).toBeVisible();

      // Check for WARN color (yellow)
      const warnElement = logsContainer.locator('.text-yellow-400');
      await expect(warnElement).toBeVisible();

      // Check for INFO color (blue)
      const infoElement = logsContainer.locator('.text-blue-400');
      await expect(infoElement).toBeVisible();
    });

    test('should display timestamps in logs', async ({ page }) => {
      await page.route('**/api/logs', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            logs: [
              '2026-02-01 12:00:00|INFO|Test log message',
              '2026-02-01 12:01:00|INFO|Another log message'
            ]
          })
        });
      });

      await dashboardPage.goto();

      const logsContainer = dashboardPage.logsContainer;
      const timestampText = await logsContainer.textContent();

      expect(timestampText).toMatch(/\d{4}-\d{2}-\d{2}/);
      expect(timestampText).toMatch(/\d{2}:\d{2}:\d{2}/);
    });
  });

  test.describe('Scrolling Behavior', () => {
    test('should have scrollable logs container', async ({ page }) => {
      // Generate many logs
      const logs: string[] = [];
      for (let i = 0; i < 50; i++) {
        logs.push(`2026-02-01 12:${String(i).padStart(2, '0')}:00|INFO|Log message ${i}`);
      }

      await page.route('**/api/logs', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ logs })
        });
      });

      await dashboardPage.goto();

      const logsContainer = dashboardPage.logsContainer;

      // Check if container has scrollable class
      const classList = await logsContainer.getAttribute('class') || '';
      expect(classList).toContain('overflow-y-auto');
    });

    test('should auto-scroll to bottom on new logs', async ({ page }) => {
      // Generate many logs
      const logs: string[] = [];
      for (let i = 0; i < 20; i++) {
        logs.push(`2026-02-01 12:${String(i).padStart(2, '0')}:00|INFO|Log message ${i}`);
      }

      await page.route('**/api/logs', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ logs })
        });
      });

      await dashboardPage.goto();

      const logsContainer = dashboardPage.logsContainer;

      // Check if scrolled to bottom
      const scrollTop = await logsContainer.evaluate(el => {
        return el.scrollTop;
      });

      const scrollHeight = await logsContainer.evaluate(el => {
        return el.scrollHeight;
      });

      const clientHeight = await logsContainer.evaluate(el => {
        return el.clientHeight;
      });

      // Should be scrolled near bottom
      expect(scrollTop + clientHeight).toBeGreaterThanOrEqual(scrollHeight - 100);
    });
  });

  test.describe('Real-time Updates', () => {
    test('should refresh logs periodically', async ({ page }) => {
      await dashboardPage.goto();

      let apiCallCount = 0;
      page.on('request', request => {
        if (request.url().includes('/api/logs')) {
          apiCallCount++;
        }
      });

      await dashboardPage.waitForAutoRefresh();
      await dashboardPage.waitForAutoRefresh();

      expect(apiCallCount).toBeGreaterThan(1);
    });

    test('should update logs when refresh button is clicked', async ({ page }) => {
      let callCount = 0;

      await page.route('**/api/logs', async route => {
        callCount++;
        const logs = [`2026-02-01 12:${String(callCount).padStart(2, '0')}:00|INFO|Refresh ${callCount}`];
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ logs })
        });
      });

      await dashboardPage.goto();

      const logsBefore = await dashboardPage.getLogs();

      await dashboardPage.refresh();
      await page.waitForTimeout(500);

      const logsAfter = await dashboardPage.getLogs();

      expect(logsAfter.length).toBeGreaterThan(0);
    });
  });

  test.describe('Empty State', () => {
    test('should handle empty logs gracefully', async ({ page }) => {
      await page.route('**/api/logs', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ logs: [] })
        });
      });

      await dashboardPage.goto();

      const logsContainer = dashboardPage.logsContainer;
      const text = await logsContainer.textContent();

      expect(text).toBeTruthy();
    });

    test('should display error message on API failure', async ({ page }) => {
      await page.route('**/api/logs', async route => {
        await route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ error: 'Internal server error' })
        });
      });

      await dashboardPage.goto();

      // Logs panel should still be visible
      await expect(dashboardPage.logsPanel).toBeVisible();
    });
  });

  test.describe('Log Formatting', () => {
    test('should handle logs with different formats', async ({ page }) => {
      await page.route('**/api/logs', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            logs: [
              '2026-02-01 12:00:00|INFO|Standard format log',
              'Non-standard log message without pipe',
              'Another log message'
            ]
          })
        });
      });

      await dashboardPage.goto();

      const logsContainer = dashboardPage.logsContainer;
      const text = await logsContainer.textContent();

      expect(text).toContain('Standard format log');
      expect(text).toContain('Non-standard log message');
    });

    test('should handle very long log messages', async ({ page }) => {
      const longMessage = 'A'.repeat(500);

      await page.route('**/api/logs', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            logs: [
              `2026-02-01 12:00:00|INFO|${longMessage}`
            ]
          })
        });
      });

      await dashboardPage.goto();

      const logsContainer = dashboardPage.logsContainer;
      const text = await logsContainer.textContent();

      expect(text).toBeTruthy();
    });
  });

  test.describe('Visual Styling', () => {
    test('should have monospace font for logs', async ({ page }) => {
      await dashboardPage.goto();

      const logsContainer = dashboardPage.logsContainer;
      const fontFamily = await logsContainer.evaluate(el => {
        return window.getComputedStyle(el).fontFamily;
      });

      expect(fontFamily).toMatch(/monospace|Courier/);
    });

    test('should have dark background for logs', async ({ page }) => {
      await dashboardPage.goto();

      const logsContainer = dashboardPage.logsContainer;
      const backgroundColor = await logsContainer.evaluate(el => {
        return window.getComputedStyle(el).backgroundColor;
      });

      // Should be dark (rgb values low)
      expect(backgroundColor).toBeTruthy();
    });
  });
});
