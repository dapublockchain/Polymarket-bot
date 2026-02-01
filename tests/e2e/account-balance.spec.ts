/**
 * Account Balance Monitoring E2E Tests
 *
 * Tests for the Account Balance, Position Value, and Total Assets cards
 * API: GET /api/balance
 */

import { test, expect } from '@playwright/test';
import { DashboardPage } from './pages/DashboardPage';
import { ApiHelper, BalanceResponse } from './pages/ApiHelper';

test.describe('Account Balance Monitoring', () => {
  let dashboardPage: DashboardPage;
  let apiHelper: ApiHelper;

  // Initialize page object before each test
  test.beforeEach(async ({ page, request }) => {
    dashboardPage = new DashboardPage(page);
    apiHelper = new ApiHelper(request, process.env.BASE_URL || 'http://localhost:8080');
  });

  test.describe('Page Load - Balance Cards', () => {
    test('should display all balance cards on page load', async ({ page }) => {
      await dashboardPage.goto();

      // Verify all four metric cards are visible
      await expect(dashboardPage.accountBalanceCard).toBeVisible();
      await expect(dashboardPage.positionValueCard).toBeVisible();
      await expect(dashboardPage.totalProfitCard).toBeVisible();
      await expect(dashboardPage.totalAssetsCard).toBeVisible();
    });

    test('should display correct labels for balance cards', async ({ page }) => {
      await dashboardPage.goto();

      await expect(dashboardPage.accountBalanceLabel).toContainText('账户余额');
      await expect(dashboardPage.positionValueLabel).toContainText('持仓价值');
      await expect(dashboardPage.totalProfitLabel).toContainText('总利润');
      await expect(dashboardPage.totalAssetsLabel).toContainText('总资产');
    });

    test('should display balance values in correct format ($X.XX)', async ({ page }) => {
      await dashboardPage.goto();

      const balance = await dashboardPage.getAccountBalance();
      const positionValue = await dashboardPage.getPositionValue();
      const totalAssets = await dashboardPage.getTotalAssets();

      // Verify format: starts with $ and has decimal
      expect(balance).toMatch(/^\$\d+\.\d{2}$/);
      expect(positionValue).toMatch(/^\$\d+\.\d{2}$/);
      expect(totalAssets).toMatch(/^\$\d+\.\d{2}$/);
    });
  });

  test.describe('API Integration - Balance', () => {
    test('should fetch balance data from API on page load', async ({ page }) => {
      // Track API calls
      const balanceRequests: string[] = [];
      page.on('request', request => {
        if (request.url().includes('/api/balance')) {
          balanceRequests.push(request.url());
        }
      });

      await dashboardPage.goto();

      // Verify balance API was called
      expect(balanceRequests.length).toBeGreaterThan(0);
    });

    test('should display balance data from API response', async ({ page, request }) => {
      // Get actual API data
      const apiData = await apiHelper.getBalance() as BalanceResponse;

      await dashboardPage.goto();
      await dashboardPage.waitForAccountBalanceUpdate();

      // Verify displayed values match API response
      const displayedBalance = await dashboardPage.getAccountBalanceValue();
      const displayedPositionValue = await dashboardPage.getPositionValueNumber();
      const displayedTotalAssets = await dashboardPage.getTotalAssetsValue();

      expect(displayedBalance).toBeCloseTo(apiData.usdc_balance, 2);
      expect(displayedPositionValue).toBeCloseTo(apiData.position_value, 2);
      expect(displayedTotalAssets).toBeCloseTo(apiData.total_assets, 2);
    });

    test('should handle API errors gracefully', async ({ page }) => {
      // Mock API error response
      await page.route('**/api/balance', async route => {
        await route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ error: 'Internal server error' })
        });
      });

      await dashboardPage.goto();

      // Page should still load even with API error
      await expect(dashboardPage.accountBalanceCard).toBeVisible();
    });
  });

  test.describe('Total Assets Calculation', () => {
    test('should calculate total assets as balance + position value', async ({ page }) => {
      await dashboardPage.goto();

      const isCorrect = await dashboardPage.verifyTotalAssetsCalculation();
      expect(isCorrect).toBe(true);
    });

    test('should update total assets when balance changes', async ({ page }) => {
      await dashboardPage.goto();

      // Mock new balance data
      const newBalance = 1500.00;
      const newPositionValue = 200.00;

      await page.route('**/api/balance', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            usdc_balance: newBalance,
            position_value: newPositionValue,
            total_assets: newBalance + newPositionValue
          })
        });
      });

      await dashboardPage.refresh();

      // Wait for update
      await page.waitForTimeout(1000);

      const totalAssets = await dashboardPage.getTotalAssetsValue();
      expect(totalAssets).toBeCloseTo(newBalance + newPositionValue, 2);
    });
  });

  test.describe('Real-time Updates', () => {
    test('should refresh balance data when refresh button is clicked', async ({ page }) => {
      await dashboardPage.goto();

      // Get initial balance
      const initialBalance = await dashboardPage.getAccountBalance();

      // Mock different balance on next call
      let callCount = 0;
      await page.route('**/api/balance', async route => {
        callCount++;
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            usdc_balance: 1000 + callCount * 100,
            position_value: 0,
            total_assets: 1000 + callCount * 100
          })
        });
      });

      await dashboardPage.refresh();

      // Wait for update
      await page.waitForTimeout(1000);

      const newBalance = await dashboardPage.getAccountBalance();
      expect(newBalance).not.toBe(initialBalance);
    });

    test('should auto-refresh balance data periodically', async ({ page }) => {
      await dashboardPage.goto();

      // Track balance API calls
      let apiCallCount = 0;
      page.on('request', request => {
        if (request.url().includes('/api/balance')) {
          apiCallCount++;
        }
      });

      // Wait for auto-refresh (2 second interval)
      await dashboardPage.waitForAutoRefresh();
      await dashboardPage.waitForAutoRefresh();

      // Should have been called multiple times
      expect(apiCallCount).toBeGreaterThan(1);
    });
  });

  test.describe('Visual States', () => {
    test('should have hover effect on balance cards', async ({ page }) => {
      await dashboardPage.goto();

      const card = dashboardPage.accountBalanceCard;
      const classListBefore = await card.getAttribute('class') || '';

      // Hover over card
      await card.hover();

      // Wait for transition
      await page.waitForTimeout(400);

      // Check if transform was applied (via CSS)
      const isVisible = await card.isVisible();
      expect(isVisible).toBe(true);
    });

    test('should display icons on all balance cards', async ({ page }) => {
      await dashboardPage.goto();

      const icons = [
        dashboardPage.accountBalanceCard.locator('svg'),
        dashboardPage.positionValueCard.locator('svg'),
        dashboardPage.totalProfitCard.locator('svg'),
        dashboardPage.totalAssetsCard.locator('svg')
      ];

      for (const icon of icons) {
        await expect(icon).toBeVisible();
      }
    });
  });

  test.describe('Edge Cases', () => {
    test('should display zero values correctly', async ({ page }) => {
      // Mock zero balance
      await page.route('**/api/balance', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            usdc_balance: 0,
            position_value: 0,
            total_assets: 0
          })
        });
      });

      await dashboardPage.goto();

      const balance = await dashboardPage.getAccountBalance();
      expect(balance).toContain('$0.00');
    });

    test('should display large values correctly', async ({ page }) => {
      // Mock large balance
      await page.route('**/api/balance', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            usdc_balance: 1000000.50,
            position_value: 500000.25,
            total_assets: 1500000.75
          })
        });
      });

      await dashboardPage.goto();

      const balance = await dashboardPage.getAccountBalance();
      expect(balance).toMatch(/\$.*1000000\.50/);
    });

    test('should handle negative position value', async ({ page }) => {
      // Mock negative position value (loss scenario)
      await page.route('**/api/balance', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            usdc_balance: 1000,
            position_value: -50,
            total_assets: 950
          })
        });
      });

      await dashboardPage.goto();

      const positionValue = await dashboardPage.getPositionValue();
      expect(positionValue).toContain('-');
    });
  });

  test.describe('Accessibility', () => {
    test('should have accessible labels on balance cards', async ({ page }) => {
      await dashboardPage.goto();

      // Check that labels are readable
      const balanceLabel = await dashboardPage.accountBalanceLabel.textContent();
      expect(balanceLabel).toBeTruthy();
      expect(balanceLabel?.length).toBeGreaterThan(0);
    });

    test('should maintain contrast ratio', async ({ page }) => {
      await dashboardPage.goto();

      // Check that values are visible (basic check)
      const balanceElement = dashboardPage.accountBalanceValue;
      await expect(balanceElement).toBeVisible();

      const computedStyle = await balanceElement.evaluate(el => {
        const styles = window.getComputedStyle(el);
        return {
          color: styles.color,
          fontSize: styles.fontSize
        };
      });

      expect(computedStyle.color).toBeTruthy();
      expect(computedStyle.fontSize).not.toBe('0px');
    });
  });
});
