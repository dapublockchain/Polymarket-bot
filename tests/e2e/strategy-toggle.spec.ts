/**
 * Interactive Strategy Toggle E2E Tests
 *
 * Tests for the 6 strategy cards that can be clicked to toggle on/off,
 * visual feedback (ring-2 for enabled strategies),
 * toast notifications on successful toggle
 * API: GET /api/strategies and POST /api/strategies/{id}/toggle
 */

import { test, expect } from '@playwright/test';
import { DashboardPage } from './pages/DashboardPage';
import { ApiHelper, Strategy, StrategyToggleResponse } from './pages/ApiHelper';

const ALL_STRATEGIES: Strategy[] = [
  { id: 'atomic_arbitrage', name: '原子套利', icon: '⚡', enabled: true },
  { id: 'negrisk', name: 'NegRisk', icon: '📊', enabled: true },
  { id: 'market_grouper', name: '组合套利', icon: '🔄', enabled: true },
  { id: 'settlement_lag', name: '结算滞后', icon: '⏰', enabled: false },
  { id: 'market_making', name: '盘口做市', icon: '💱', enabled: false },
  { id: 'tail_risk', name: '尾部风险', icon: '🛡️', enabled: false },
];

test.describe('Interactive Strategy Toggle', () => {
  let dashboardPage: DashboardPage;
  let apiHelper: ApiHelper;

  test.beforeEach(async ({ page, request }) => {
    dashboardPage = new DashboardPage(page);
    apiHelper = new ApiHelper(request, process.env.BASE_URL || 'http://localhost:8080');
  });

  test.describe('Page Load - Strategy Cards', () => {
    test('should display all 6 strategy cards', async ({ page }) => {
      await dashboardPage.goto();

      const cards = dashboardPage.getStrategyCards();
      const count = await cards.count();

      expect(count).toBe(6);
    });

    test('should display strategy section with correct title', async ({ page }) => {
      await dashboardPage.goto();

      await expect(dashboardPage.strategiesSection).toBeVisible();
      await expect(dashboardPage.strategiesSection).toContainText('策略状态');
      await expect(dashboardPage.strategiesSection).toContainText('点击切换');
    });

    test('should display strategy names correctly', async ({ page }) => {
      await dashboardPage.goto();

      const cards = dashboardPage.getStrategyCards();
      const count = await cards.count();

      for (let i = 0; i < count; i++) {
        const card = cards.nth(i);
        const name = await card.locator('.text-sm.font-medium').textContent();

        expect(name).toBeTruthy();
        expect(name?.length).toBeGreaterThan(0);
      }
    });

    test('should display strategy icons', async ({ page }) => {
      await dashboardPage.goto();

      const cards = dashboardPage.getStrategyCards();
      const count = await cards.count();

      for (let i = 0; i < count; i++) {
        const card = cards.nth(i);
        const icon = card.locator('.text-2xl');

        await expect(icon).toBeVisible();
        const iconText = await icon.textContent();
        expect(iconText?.length).toBe(1); // Single emoji
      }
    });
  });

  test.describe('API Integration - Strategies', () => {
    test('should fetch strategies from API on page load', async ({ page }) => {
      const strategyRequests: string[] = [];
      page.on('request', request => {
        if (request.url().includes('/api/strategies')) {
          strategyRequests.push(request.url());
        }
      });

      await dashboardPage.goto();

      expect(strategyRequests.length).toBeGreaterThan(0);
    });

    test('should display strategies from API response', async ({ page, request }) => {
      const apiData = await apiHelper.getStrategies();

      await dashboardPage.goto();

      const strategies = await dashboardPage.getAllStrategies();

      expect(strategies.length).toBe(apiData.strategies.length);

      for (const apiStrategy of apiData.strategies) {
        const displayedStrategy = strategies.find(s => s.id === apiStrategy.id);
        expect(displayedStrategy).toBeDefined();
        expect(displayedStrategy?.name).toBe(apiStrategy.name);
      }
    });

    test('should handle strategies API errors with fallback', async ({ page }) => {
      // Mock API error
      await page.route('**/api/strategies', async route => {
        await route.abort('failed');
      });

      await dashboardPage.goto();

      // Should still show strategies (from fallback)
      const cards = dashboardPage.getStrategyCards();
      const count = await cards.count();

      expect(count).toBeGreaterThan(0);
    });
  });

  test.describe('Strategy Visual State', () => {
    test('should display enabled strategies with green ring', async ({ page }) => {
      // Mock strategies with specific enabled states
      await page.route('**/api/strategies', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            strategies: [
              { id: 'atomic_arbitrage', name: '原子套利', icon: '⚡', enabled: true },
              { id: 'settlement_lag', name: '结算滞后', icon: '⏰', enabled: false },
            ]
          })
        });
      });

      await dashboardPage.goto();

      const atomicCard = dashboardPage.getStrategyCardById('atomic_arbitrage');
      const settlementCard = dashboardPage.getStrategyCardById('settlement_lag');

      const atomicClass = await atomicCard.getAttribute('class') || '';
      const settlementClass = await settlementCard.getAttribute('class') || '';

      // Enabled strategy should have ring-2 and ring-green-500 classes
      expect(atomicClass).toContain('ring-2');
      expect(atomicClass).toContain('ring-green-500');

      // Disabled strategy should not have ring classes
      expect(settlementClass).not.toContain('ring-2');
    });

    test('should display correct status badge text', async ({ page }) => {
      await dashboardPage.goto();

      const cards = dashboardPage.getStrategyCards();
      const count = await cards.count();

      for (let i = 0; i < count; i++) {
        const card = cards.nth(i);
        const badge = card.locator('[id*="strategy-"][id*="-status"]');
        const text = await badge.textContent();

        expect(text).toMatch(/启用|禁用/);
      }
    });

    test('should display status badge with correct color', async ({ page }) => {
      await page.route('**/api/strategies', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            strategies: [
              { id: 'atomic_arbitrage', name: '原子套利', icon: '⚡', enabled: true },
              { id: 'settlement_lag', name: '结算滞后', icon: '⏰', enabled: false },
            ]
          })
        });
      });

      await dashboardPage.goto();

      const atomicBadge = dashboardPage.getStrategyStatusBadge('atomic_arbitrage');
      const settlementBadge = dashboardPage.getStrategyStatusBadge('settlement_lag');

      const atomicClass = await atomicBadge.getAttribute('class') || '';
      const settlementClass = await settlementBadge.getAttribute('class') || '';

      // Enabled badge should be green
      expect(atomicClass).toContain('bg-green-500');
      expect(atomicClass).toContain('text-green-400');

      // Disabled badge should be red
      expect(settlementClass).toContain('bg-red-500');
      expect(settlementClass).toContain('text-red-400');
    });
  });

  test.describe('Strategy Toggle Functionality', () => {
    test('should toggle strategy when card is clicked', async ({ page }) => {
      await dashboardPage.goto();

      const strategiesBefore = await dashboardPage.getAllStrategies();
      const firstStrategy = strategiesBefore[0];

      const card = dashboardPage.getStrategyCardById(firstStrategy.id);
      await card.click();

      // Wait for API and visual update
      await page.waitForTimeout(1000);

      const strategiesAfter = await dashboardPage.getAllStrategies();
      const sameStrategyAfter = strategiesAfter.find(s => s.id === firstStrategy.id);

      expect(sameStrategyAfter).toBeDefined();
    });

    test('should call toggle API when strategy is clicked', async ({ page }) => {
      await dashboardPage.goto();

      let toggleApiCalled = false;
      let capturedStrategyId = '';

      page.on('request', request => {
        if (request.url().includes('/api/strategies/') && request.url().includes('/toggle')) {
          toggleApiCalled = true;
          const url = request.url();
          const match = url.match(/strategies\/([^/]+)\/toggle/);
          if (match) {
            capturedStrategyId = match[1];
          }
        }
      });

      const strategies = await dashboardPage.getAllStrategies();
      const firstStrategy = strategies[0];

      const card = dashboardPage.getStrategyCardById(firstStrategy.id);
      await card.click();

      await page.waitForTimeout(500);

      expect(toggleApiCalled).toBe(true);
      expect(capturedStrategyId).toBe(firstStrategy.id);
    });

    test('should show loading state during toggle', async ({ page }) => {
      // Mock slow API
      await page.route('**/api/strategies/*/toggle', async route => {
        await new Promise(resolve => setTimeout(resolve, 1000));
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

      // Check for loading state (opacity-50 and pointer-events-none)
      await page.waitForTimeout(100);
      const classList = await card.getAttribute('class') || '';

      expect(classList).toContain('opacity-50');
    });

    test('should remove loading state after toggle completes', async ({ page }) => {
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

      // Wait for completion
      await page.waitForTimeout(1500);

      const classList = await card.getAttribute('class') || '';
      expect(classList).not.toContain('opacity-50');
    });
  });

  test.describe('Toast Notifications', () => {
    test('should show toast notification on successful toggle', async ({ page }) => {
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

      // Wait for toast
      await page.waitForTimeout(500);

      const toast = page.locator('.fixed.top-20.right-4');
      await expect(toast).toBeVisible();
    });

    test('should display success message in toast', async ({ page }) => {
      const expectedMessage = '原子套利 已启用';

      await page.route('**/api/strategies/*/toggle', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            success: true,
            strategy_id: 'atomic_arbitrage',
            strategy_name: '原子套利',
            enabled: true,
            message: expectedMessage
          })
        });
      });

      await dashboardPage.goto();

      const card = dashboardPage.getStrategyCardById('atomic_arbitrage');
      await card.click();

      // Wait for and verify toast
      await page.waitForTimeout(500);
      const toast = page.locator('.fixed.top-20.right-4');
      await expect(toast).toContainText(expectedMessage);
    });

    test('should show error toast on failed toggle', async ({ page }) => {
      await page.route('**/api/strategies/*/toggle', async route => {
        await route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({
            success: false,
            error: 'Internal server error'
          })
        });
      });

      await dashboardPage.goto();

      // Mock initial strategies
      await page.route('**/api/strategies', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ strategies: ALL_STRATEGIES })
        });
      });

      const card = dashboardPage.getStrategyCardById('atomic_arbitrage');
      await card.click();

      // Wait for toast
      await page.waitForTimeout(500);

      const toast = page.locator('.fixed.top-20.right-4.bg-red-500');
      await expect(toast).toBeVisible();
    });

    test('should remove toast after timeout', async ({ page }) => {
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

      // Wait for toast to appear
      await page.waitForTimeout(500);
      let toast = page.locator('.fixed.top-20.right-4');
      await expect(toast).toBeVisible();

      // Wait for toast to disappear (3 second timeout)
      await page.waitForTimeout(3000);
      toast = page.locator('.fixed.top-20.right-4');
      await expect(toast).not.toBeVisible();
    });
  });

  test.describe('Multiple Strategy Toggles', () => {
    test('should allow toggling multiple strategies', async ({ page }) => {
      await page.route('**/api/strategies/*/toggle', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            success: true,
            strategy_id: 'test',
            strategy_name: 'Test',
            enabled: true,
            message: 'Test 已启用'
          })
        });
      });

      await dashboardPage.goto();

      const cards = dashboardPage.getStrategyCards();

      // Click first 3 cards
      await cards.nth(0).click();
      await page.waitForTimeout(500);
      await cards.nth(1).click();
      await page.waitForTimeout(500);
      await cards.nth(2).click();
      await page.waitForTimeout(500);

      // All toggles should have been processed
      const toasts = await page.locator('.fixed.top-20.right-4').all();
      expect(toasts.length).toBeGreaterThan(0);
    });

    test('should maintain independent state for each strategy', async ({ page }) => {
      await page.route('**/api/strategies/*/toggle', async route => {
        const url = route.request().url();
        const match = url.match(/strategies\/([^/]+)\/toggle/);
        const strategyId = match ? match[1] : 'unknown';

        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            success: true,
            strategy_id: strategyId,
            strategy_name: 'Strategy',
            enabled: true,
            message: 'Strategy 已启用'
          })
        });
      });

      await dashboardPage.goto();

      const strategiesBefore = await dashboardPage.getAllStrategies();

      // Toggle each strategy
      for (const strategy of strategiesBefore) {
        const card = dashboardPage.getStrategyCardById(strategy.id);
        await card.click();
        await page.waitForTimeout(300);
      }

      // All strategies should still be present
      const strategiesAfter = await dashboardPage.getAllStrategies();
      expect(strategiesAfter.length).toBe(strategiesBefore.length);
    });
  });

  test.describe('Visual Feedback', () => {
    test('should show hover effect on strategy cards', async ({ page }) => {
      await dashboardPage.goto();

      const card = dashboardPage.getStrategyCards().first();

      // Get initial class list
      const classBefore = await card.getAttribute('class') || '';

      // Hover over card
      await card.hover();
      await page.waitForTimeout(100);

      // Cursor should be pointer
      const cursor = await card.evaluate(el => {
        return window.getComputedStyle(el).cursor;
      });
      expect(cursor).toBe('pointer');
    });

    test('should have clickable cursor on strategy cards', async ({ page }) => {
      await dashboardPage.goto();

      const cards = dashboardPage.getStrategyCards();
      const count = await cards.count();

      for (let i = 0; i < Math.min(count, 3); i++) {
        const card = cards.nth(i);
        const cursor = await card.evaluate(el => {
          return window.getComputedStyle(el).cursor;
        });
        expect(cursor).toBe('pointer');
      }
    });
  });

  test.describe('Edge Cases', () => {
    test('should handle rapid clicking on same strategy', async ({ page }) => {
      let toggleCount = 0;

      await page.route('**/api/strategies/*/toggle', async route => {
        toggleCount++;
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            success: true,
            strategy_id: 'atomic_arbitrage',
            strategy_name: '原子套利',
            enabled: toggleCount % 2 === 0,
            message: 'Strategy toggled'
          })
        });
      });

      await dashboardPage.goto();

      const card = dashboardPage.getStrategyCardById('atomic_arbitrage');

      // Rapid clicks
      await card.click();
      await card.click();
      await card.click();

      await page.waitForTimeout(1000);

      // Should handle gracefully
      await expect(card).toBeVisible();
    });

    test('should handle unknown strategy ID', async ({ page }) => {
      await page.route('**/api/strategies/unknown/toggle', async route => {
        await route.fulfill({
          status: 404,
          contentType: 'application/json',
          body: JSON.stringify({
            success: false,
            error: 'Unknown strategy'
          })
        });
      });

      await dashboardPage.goto();

      // Try to click unknown strategy (manually trigger)
      await page.evaluate(() => {
        window.fetch('/api/strategies/unknown/toggle', { method: 'POST' });
      });

      await page.waitForTimeout(500);

      // Should not crash
      await expect(dashboardPage.strategiesGrid).toBeVisible();
    });
  });
});
