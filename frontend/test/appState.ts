import { vi } from 'vitest';
import type { ApiPortfolio, PriceUpdate, WatchlistItem } from '@/lib/types';

// Builds a fully-populated AppState-shaped object for component tests that mock
// the store. Override any slice per test.
export function makeAppState(overrides: Record<string, unknown> = {}) {
  return {
    prices: {} as Record<string, PriceUpdate>,
    sparklines: {} as Record<string, number[]>,
    status: 'connected' as const,
    portfolio: null as ApiPortfolio | null,
    history: [],
    watchlist: [] as WatchlistItem[],
    selectedTicker: null as string | null,
    chatMessages: [],
    chatLoading: false,
    actionError: null as string | null,
    selectTicker: vi.fn(),
    executeTrade: vi.fn().mockResolvedValue(true),
    addTicker: vi.fn().mockResolvedValue(true),
    removeTicker: vi.fn().mockResolvedValue(undefined),
    sendChat: vi.fn().mockResolvedValue(undefined),
    clearActionError: vi.fn(),
    ...overrides,
  };
}

export function priceUpdate(
  ticker: string,
  price: number,
  changePct = 0,
): PriceUpdate {
  return {
    ticker,
    price,
    previous_price: price,
    change_direction: changePct >= 0 ? 'up' : 'down',
    change_pct: changePct,
    timestamp: new Date().toISOString(),
  };
}
