import { test, expect } from '@playwright/test';
import { gotoApp, tickerRow, headerMetric, readMoney } from './helpers';

const TICKER = 'NVDA';
const QTY = 2;

test('sell shares: cash increases, position disappears when fully sold', async ({ page }) => {
  await gotoApp(page);

  // Setup: buy a position we can then sell.
  await page.getByLabel('Trade ticker').fill(TICKER);
  await page.getByLabel('Trade quantity').fill(String(QTY));
  await page.getByRole('button', { name: 'Buy', exact: true }).click();
  await expect(tickerRow(page, 'Positions', TICKER)).toBeVisible();

  const cashAfterBuy = await readMoney(headerMetric(page, 'Cash'));

  // Sell the whole position.
  await page.getByLabel('Trade ticker').fill(TICKER);
  await page.getByLabel('Trade quantity').fill(String(QTY));
  await page.getByRole('button', { name: 'Sell', exact: true }).click();

  // Position fully sold -> row disappears from the positions table.
  await expect(tickerRow(page, 'Positions', TICKER)).toHaveCount(0);

  // Cash went back up after the sale.
  const cashAfterSell = await readMoney(headerMetric(page, 'Cash'));
  expect(cashAfterSell).toBeGreaterThan(cashAfterBuy);
});
