import { test, expect } from '@playwright/test';
import { gotoApp, panel, headerMetric, readMoney, DEFAULT_TICKERS, tickerRow } from './helpers';

// This spec assumes a freshly-seeded backend (the compose test run starts the
// app container with no persisted volume). It must run first.
test('fresh start: default watchlist, $10k cash, prices streaming', async ({ page }) => {
  await gotoApp(page);

  // All 10 default tickers appear in the watchlist.
  for (const ticker of DEFAULT_TICKERS) {
    await expect(tickerRow(page, 'Watchlist', ticker)).toBeVisible();
  }

  // $10,000 cash on a fresh portfolio.
  await expect(headerMetric(page, 'Cash')).toHaveText('$10,000.00');
  expect(await readMoney(headerMetric(page, 'Portfolio Value'))).toBeCloseTo(10000, 0);

  // Prices are streaming: a watchlist price cell updates within a few seconds.
  const priceCell = tickerRow(page, 'Watchlist', 'AAPL').locator('td').nth(1);
  const first = (await priceCell.innerText()).trim();
  await expect
    .poll(async () => (await priceCell.innerText()).trim(), { timeout: 15_000 })
    .not.toBe(first);
});
