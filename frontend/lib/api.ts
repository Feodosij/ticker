// All network calls to the FastAPI backend live here so they are trivial to
// mock in tests and to verify against the live server. Same-origin, relative URLs.

import type {
  ApiPortfolio,
  ChatResponse,
  PortfolioSnapshot,
  TradeRequest,
  TradeResult,
  WatchlistItem,
} from './types';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // non-JSON error body; keep status text
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  getPortfolio: () => request<ApiPortfolio>('/api/portfolio'),

  getPortfolioHistory: () =>
    request<PortfolioSnapshot[]>('/api/portfolio/history'),

  trade: (body: TradeRequest) =>
    request<TradeResult>('/api/portfolio/trade', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  getWatchlist: () => request<WatchlistItem[]>('/api/watchlist'),

  // Backend returns the single (possibly pre-existing) entry; idempotent.
  addWatchlist: (ticker: string) =>
    request<WatchlistItem>('/api/watchlist', {
      method: 'POST',
      body: JSON.stringify({ ticker: ticker.toUpperCase() }),
    }),

  // 204 No Content on success.
  removeWatchlist: (ticker: string) =>
    request<void>(`/api/watchlist/${encodeURIComponent(ticker.toUpperCase())}`, {
      method: 'DELETE',
    }),

  chat: (message: string) =>
    request<ChatResponse>('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ message }),
    }),

  health: () => request<{ status: string }>('/api/health'),
};

export const PRICE_STREAM_URL = '/api/stream/prices';
