import { test, expect } from '@playwright/test';
import { gotoApp, panel, tickerRow, headerMetric, readMoney } from './helpers';

// Mock LLM contract (LLM_MOCK=true): a message containing "buy" buys 1 share of
// the first watchlist ticker (AAPL). The reply + executed trade appear inline in
// the chat, and the trade is reflected in the positions table and cash balance.
test('AI chat (mocked): buy message executes a trade shown inline and in portfolio', async ({ page }) => {
  await gotoApp(page);

  const cashBefore = await readMoney(headerMetric(page, 'Cash'));

  const composer = page.getByLabel('Message Ticker');
  await composer.fill('please buy something for me');
  await composer.press('Enter');

  // Assistant reply bubble.
  await expect(page.getByText('Buying 1 share of AAPL.')).toBeVisible();

  // Executed trade shown inline as a confirmation chip in the chat.
  await expect(page.getByText(/Bought\s+1\s+AAPL\s+@/)).toBeVisible();

  // Reflected in the positions table.
  await expect(tickerRow(page, 'Positions', 'AAPL')).toBeVisible();

  // Reflected in the cash balance.
  await expect
    .poll(async () => readMoney(headerMetric(page, 'Cash')), { timeout: 10_000 })
    .toBeLessThan(cashBefore);
});
