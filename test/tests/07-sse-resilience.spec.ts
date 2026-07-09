import { test, expect } from '@playwright/test';
import { gotoApp, connectionDot } from './helpers';

const STREAM = '**/api/stream/prices';

test('SSE resilience: connected -> disconnect -> recovers', async ({ page }) => {
  await gotoApp(page);

  // Header indicator reflects a live connection.
  await expect(connectionDot(page)).toHaveAttribute('data-status', 'connected', { timeout: 15_000 });

  // Simulate a disconnect: block the SSE endpoint, then reload so the fresh
  // EventSource fails to connect and the UI reports it.
  await page.route(STREAM, (route) => route.abort());
  await page.reload();
  await expect(connectionDot(page).first()).toBeVisible();
  await expect
    .poll(async () => connectionDot(page).first().getAttribute('data-status'), { timeout: 20_000 })
    .not.toBe('connected'); // reconnecting or disconnected

  // Restore the endpoint; EventSource auto-retries and the UI recovers.
  await page.unroute(STREAM);
  await expect(connectionDot(page).first()).toHaveAttribute('data-status', 'connected', {
    timeout: 25_000,
  });
});
