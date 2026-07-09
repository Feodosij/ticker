import { Page, Locator, expect } from '@playwright/test';

export const DEFAULT_TICKERS = [
  'AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA', 'NVDA', 'META', 'JPM', 'V', 'NFLX',
];

/** A dashboard panel (<section>) located by its header title. */
export function panel(page: Page, title: string): Locator {
  return page
    .locator('section')
    .filter({ has: page.getByRole('heading', { name: title, exact: true }) });
}

/** Navigate to the app and wait for the watchlist to populate from the API. */
export async function gotoApp(page: Page): Promise<void> {
  await page.goto('/');
  await expect(panel(page, 'Watchlist').locator('tbody tr').first()).toBeVisible();
}

/** A header metric value span, located by its (exact) label text. */
export function headerMetric(page: Page, label: string): Locator {
  return page.getByText(label, { exact: true }).locator('xpath=following-sibling::span[1]');
}

/** Parse a "$10,000.00" style money string into a number. */
export async function readMoney(loc: Locator): Promise<number> {
  const txt = await loc.innerText();
  return parseFloat(txt.replace(/[^0-9.\-]/g, ''));
}

/** The header connection-status dot; its data-status is one of
 * connected | reconnecting | disconnected. */
export function connectionDot(page: Page): Locator {
  return page.locator('[data-status]');
}

/** A row in a given panel's table whose ticker cell equals the symbol exactly
 * (so "V" does not match the "NVDA" row). */
export function tickerRow(page: Page, panelTitle: string, ticker: string): Locator {
  return panel(page, panelTitle)
    .locator('tbody tr')
    .filter({ has: page.getByRole('cell', { name: ticker, exact: true }) });
}

/** Read the current cash balance from the API (authoritative). */
export async function apiCash(page: Page): Promise<number> {
  const res = await page.request.get('/api/portfolio');
  const body = await res.json();
  return body.cash_balance as number;
}
