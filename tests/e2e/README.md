# PolyArb-X E2E Tests

Playwright end-to-end tests for the PolyArb-X Dashboard at `http://localhost:8080`.

## Overview

This test suite covers all interactive features of the PolyArb-X trading dashboard:

1. **Account Balance Monitoring** - Balance, Position Value, Total Assets cards
2. **Real-time Profit Display** - Total Profit, Average Profit per Trade, Performance Chart
3. **Interactive Strategy Toggle** - 6 strategy cards with on/off toggle, visual feedback, toast notifications
4. **System Status Panel** - Run mode, subscribed markets, circuit breaker status
5. **Recent Trades Table** - Trade history with profit indicators
6. **Live Logs Viewer** - Real-time log streaming with color-coded levels

## Project Structure

```
tests/e2e/
├── playwright.config.ts      # Playwright configuration
├── tsconfig.json             # TypeScript configuration
├── package.json              # NPM dependencies
├── pages/                    # Page Object Models
│   ├── DashboardPage.ts      # Main dashboard page object
│   └── ApiHelper.ts          # API helper utilities
├── fixtures/                 # Test fixtures and data
│   └── test-data.ts          # Shared test data
├── account-balance.spec.ts   # Account balance tests
├── profit-display.spec.ts    # Profit display tests
├── strategy-toggle.spec.ts   # Strategy toggle tests
├── system-status.spec.ts     # System status tests
├── recent-trades.spec.ts     # Recent trades tests
├── live-logs.spec.ts         # Live logs tests
└── smoke.spec.ts             # Smoke tests
```

## Installation

1. **Install Node.js dependencies:**

```bash
cd /path/to/polyarb-x
npm install
```

2. **Install Playwright browsers:**

```bash
npm run test:e2e:install
```

## Running Tests

### Run All Tests

```bash
npm run test:e2e
```

### Run With UI (Interactive Mode)

```bash
npm run test:e2e:ui
```

### Run in Headed Mode (See Browser)

```bash
npm run test:e2e:headed
```

### Run Specific Test File

```bash
npx playwright test tests/e2e/account-balance.spec.ts
```

### Run Specific Test

```bash
npx playwright test tests/e2e/strategy-toggle.spec.ts -g "should toggle strategy"
```

### Debug Tests

```bash
npm run test:e2e:debug
```

### Run in Specific Browser

```bash
npm run test:e2e:chromium
npx playwright test --project=firefox
npx playwright test --project=webkit
```

## View Test Reports

After running tests, view the HTML report:

```bash
npm run test:e2e:report
```

Or open manually:

```bash
npx playwright show-report playwright-report
```

## Test Coverage

### Account Balance (`account-balance.spec.ts`)

- Page load - Balance cards visibility
- API integration - `/api/balance` endpoint
- Total assets calculation verification
- Real-time updates
- Visual states and hover effects
- Edge cases (zero values, large values, negative values)
- Accessibility

### Profit Display (`profit-display.spec.ts`)

- Page load - Profit cards visibility
- API integration - `/api/profit` endpoint
- Performance chart rendering
- Chart period selection
- Real-time updates
- Profit calculation verification
- Visual states for positive/negative profit
- Chart features and responsiveness

### Strategy Toggle (`strategy-toggle.spec.ts`)

- Page load - Strategy cards visibility
- API integration - `/api/strategies` and `/api/strategies/{id}/toggle`
- Visual state (ring-2 for enabled strategies)
- Strategy toggle functionality
- Toast notifications (success and error)
- Multiple strategy toggles
- Visual feedback and hover effects
- Edge cases (rapid clicking, unknown strategy)

### System Status (`system-status.spec.ts`)

- Page load - Status panel visibility
- API integration - `/api/status` endpoint
- Status metrics display
- Status badge styling
- Real-time updates
- Header status indicators
- Edge cases

### Recent Trades (`recent-trades.spec.ts`)

- Page load - Trades table visibility
- Empty state handling
- Trades display from API
- Color-coded profit values
- Status badges
- Table limit (50 trades max)
- Real-time updates
- Table styling

### Live Logs (`live-logs.spec.ts`)

- Page load - Logs panel visibility
- API integration - `/api/logs` endpoint
- Log entry display with proper structure
- Color-coded log levels (INFO, ERROR, WARN, DEBUG)
- Timestamp formatting
- Scrolling behavior and auto-scroll
- Real-time updates
- Empty state handling
- Log formatting

### Smoke Tests (`smoke.spec.ts`)

- Critical user journeys
- Page load verification
- All major sections visibility
- Account balance verification
- Strategy toggle functionality
- Performance chart
- Real-time updates
- System status
- Recent trades
- Live logs
- Regression tests
- API integration tests

## API Endpoints Tested

| Endpoint | Method | Tests |
|----------|--------|-------|
| `/api/status` | GET | System Status, Smoke |
| `/api/balance` | GET | Account Balance, Smoke |
| `/api/profit` | GET | Profit Display, Smoke |
| `/api/strategies` | GET | Strategy Toggle, Smoke |
| `/api/strategies/{id}/toggle` | POST | Strategy Toggle |
| `/api/logs` | GET | Live Logs, Smoke |
| `/api/opportunities` | GET | Recent Trades, Smoke |

## Page Object Model

### DashboardPage

Main page object for the dashboard. Provides methods for:

- Navigation and page loading
- API response interception
- Account balance operations
- Position value operations
- Total profit operations
- Strategy toggle operations
- Chart operations
- Trades table operations
- System status operations
- Logs operations
- Toast notification verification
- Visual verification

### ApiHelper

Helper class for direct API calls and response mocking:

- Direct API calls without UI
- API route mocking
- Response interception
- Test data generation

## Configuration

### Environment Variables

- `BASE_URL` - Dashboard URL (default: `http://localhost:8080`)

### Playwright Config

Located in `tests/e2e/playwright.config.ts`:

- Base URL: `http://localhost:8080`
- Test timeout: 30 seconds
- Auto-wait for elements: Enabled
- Screenshot on failure: Enabled
- Video on failure: Enabled
- Trace on retry: Enabled
- Parallel execution: Enabled
- Retry on CI: 2 times

## Writing New Tests

1. **Create a new test file:**

```typescript
import { test, expect } from '@playwright/test';
import { DashboardPage } from './pages/DashboardPage';

test.describe('New Feature', () => {
  test('should do something', async ({ page }) => {
    const dashboard = new DashboardPage(page);
    await dashboard.goto();

    // Your test code here
    await expect(dashboard.someElement).toBeVisible();
  });
});
```

2. **Add methods to DashboardPage if needed:**

```typescript
// In pages/DashboardPage.ts
readonly someElement: Locator;

constructor(page: Page) {
  this.page = page;
  this.someElement = page.locator('[data-testid="some-element"]');
}

async someAction(): Promise<void> {
  await this.someElement.click();
}
```

3. **Run the new test:**

```bash
npx playwright test tests/e2e/your-new-test.spec.ts
```

## Best Practices

1. **Use Page Object Model** - Keep test logic separate from page structure
2. **Use data-testid attributes** - More stable than CSS selectors
3. **Wait for elements properly** - Use Playwright's auto-wait
4. **Avoid hard-coded waits** - Use `waitForResponse` or `waitForSelector`
5. **Mock API responses for consistency** - Use `ApiHelper.mock*` methods
6. **Test both happy path and edge cases** - Cover error scenarios
7. **Use descriptive test names** - Should explain what is being tested
8. **Keep tests independent** - Each test should work in isolation
9. **Clean up after tests** - Use `test.afterEach` if needed
10. **Take screenshots on failure** - Already configured in playwright.config.ts

## Troubleshooting

### Tests Timeout

- Increase timeout in `playwright.config.ts`
- Check if server is running on `http://localhost:8080`

### Element Not Found

- Verify the dashboard is loaded
- Check if selectors are correct
- Use the Playwright Inspector: `npx playwright test --debug`

### Flaky Tests

- Use retry mechanism in `playwright.config.ts`
- Add explicit waits for dynamic content
- Check for race conditions

### API Errors

- Verify backend server is running
- Check API endpoints are accessible
- Mock API responses for consistent testing

## CI/CD Integration

Example GitHub Actions workflow:

```yaml
name: E2E Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: 18
      - run: npm install
      - run: npx playwright install --with-deps
      - run: npm run test:e2e
      - uses: actions/upload-artifact@v3
        if: always()
        with:
          name: playwright-report
          path: playwright-report/
          retention-days: 30
```

## Success Metrics

After E2E test run:
- All critical journeys passing (100%)
- Pass rate > 95% overall
- Flaky rate < 5%
- No failed tests blocking deployment
- Artifacts uploaded and accessible
- Test duration < 5 minutes
- HTML report generated

## License

Same as parent PolyArb-X project.
