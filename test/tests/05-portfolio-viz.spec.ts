import { test, expect } from '@playwright/test';
import { gotoApp, panel, tickerRow } from './helpers';

// Ensure at least one position and >= 2 portfolio snapshots exist regardless of
// test order, then assert the heatmap + P&L chart render.
test('portfolio visualization: heatmap colored by P&L, P&L chart has data', async ({ page }) => {
  await gotoApp(page);

  // Two buys guarantee >= 2 positions/snapshots so the P&L chart has >= 2 points.
  for (const [ticker, qty] of [['MSFT', '1'], ['AAPL', '1']] as const) {
    await page.getByLabel('Trade ticker').fill(ticker);
    await page.getByLabel('Trade quantity').fill(qty);
    await page.getByRole('button', { name: 'Buy', exact: true }).click();
    await expect(tickerRow(page, 'Positions', ticker)).toBeVisible();
  }

  // Heatmap renders a treemap cell colored green/red per P&L sign.
  const heatmap = panel(page, 'Portfolio Heatmap');
  const cell = heatmap.locator('svg rect').first();
  await expect(cell).toBeVisible();
  const fill = await cell.evaluate((el) => (el as SVGElement).style.fill || el.getAttribute('fill') || '');
  // Green profit rgba(38,161,123,a) or red loss rgba(224,75,90,a).
  expect(fill.replace(/\s/g, '')).toMatch(/38,161,123|224,75,90/);

  // P&L chart shows at least one data point (placeholder is gone, area path drawn).
  const pnl = panel(page, 'Portfolio Value');
  await expect(pnl.getByText('Accruing value history')).toHaveCount(0);
  await expect(pnl.locator('svg .recharts-area-area, svg path').first()).toBeVisible();
});
