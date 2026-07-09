import { test, expect } from '@playwright/test';
import { gotoApp, panel, tickerRow, headerMetric, readMoney, apiCash } from './helpers';

const TICKER = 'MSFT';
const QTY = 2;

test('buy shares: cash decreases, position appears, portfolio updates', async ({ page }) => {
  await gotoApp(page);

  const cashBefore = await readMoney(headerMetric(page, 'Cash'));

  // Enter a trade in the trade bar and buy.
  await page.getByLabel('Trade ticker').fill(TICKER);
  await page.getByLabel('Trade quantity').fill(String(QTY));
  await page.getByRole('button', { name: 'Buy', exact: true }).click();

  // Position shows up in the positions table.
  const posRow = tickerRow(page, 'Positions', TICKER);
  await expect(posRow).toBeVisible();
  await expect(posRow.locator('td').nth(1)).toHaveText(String(QTY)); // Qty column

  // Cash decreased, by roughly qty * price (price drifts, so allow a band).
  const cashAfter = await readMoney(headerMetric(page, 'Cash'));
  expect(cashAfter).toBeLessThan(cashBefore);

  const spent = cashBefore - cashAfter;
  // MSFT ~ $420, 2 shares ~ $840; sanity-band it generously.
  expect(spent).toBeGreaterThan(200);
  expect(spent).toBeLessThan(2000);

  // Header cash matches the API's authoritative balance.
  expect(await apiCash(page)).toBeCloseTo(cashAfter, 1);
});
