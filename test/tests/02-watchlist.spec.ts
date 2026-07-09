import { test, expect } from '@playwright/test';
import { gotoApp, panel, tickerRow } from './helpers';

const NEW_TICKER = 'PLTR';

test('watchlist: add a ticker (it ticks) then remove it', async ({ page }) => {
  await gotoApp(page);

  const wl = panel(page, 'Watchlist');

  // Add via the UI input.
  await wl.getByLabel('Add ticker').fill(NEW_TICKER);
  await wl.getByRole('button', { name: '+' }).click();

  const row = tickerRow(page, 'Watchlist', NEW_TICKER);
  await expect(row).toBeVisible();

  // It eventually receives a live price (provider picks up the new ticker).
  const priceCell = row.locator('td').nth(1);
  await expect
    .poll(async () => (await priceCell.innerText()).trim(), { timeout: 20_000 })
    .not.toBe('—');

  // Remove via the row's remove button.
  await row.hover();
  await row.getByRole('button', { name: `Remove ${NEW_TICKER}` }).click();

  await expect(tickerRow(page, 'Watchlist', NEW_TICKER)).toHaveCount(0);
});
