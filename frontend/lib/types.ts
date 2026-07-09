// Shared API/domain types. Mirrors the backend contract in planning/PLAN.md §8.

export type ChangeDirection = 'up' | 'down' | 'flat';

export interface PriceUpdate {
  ticker: string;
  price: number;
  previous_price: number;
  change_direction: ChangeDirection;
  change_pct: number;
  timestamp: string;
}

// Fields are null when a ticker was just added and hasn't ticked yet.
export interface WatchlistItem {
  ticker: string;
  price: number | null;
  previous_price: number | null;
  change_direction: ChangeDirection | null;
  change_pct: number | null;
  added_at?: string;
}

// Raw position as returned by the backend (GET /api/portfolio).
export interface ApiPosition {
  ticker: string;
  quantity: number;
  avg_cost: number;
  current_price: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
}

// Raw portfolio as returned by the backend.
export interface ApiPortfolio {
  cash_balance: number;
  positions: ApiPosition[];
  total_value: number;
  total_unrealized_pnl: number;
}

// Position enriched client-side with live-price-derived fields.
export interface LivePosition extends ApiPosition {
  market_value: number;
  pnl_pct: number;
}

// Portfolio recomputed against the live SSE feed.
export interface LivePortfolio {
  cash_balance: number;
  positions: LivePosition[];
  positions_value: number;
  unrealized_pnl: number;
  total_value: number;
}

export interface PortfolioSnapshot {
  total_value: number;
  recorded_at: string;
}

export type TradeSide = 'buy' | 'sell';

export interface TradeRequest {
  ticker: string;
  quantity: number;
  side: TradeSide;
}

// POST /api/portfolio/trade response. `position` is null when a full sell emptied it.
export interface TradeResult {
  trade: {
    id: string;
    ticker: string;
    side: TradeSide;
    quantity: number;
    price: number;
    executed_at: string;
  };
  cash_balance: number;
  position: ApiPosition | null;
}

export interface ExecutedTrade {
  ticker: string;
  side: TradeSide;
  quantity: number;
  price: number;
  executed_at?: string;
  error?: string;
}

export interface WatchlistChange {
  ticker: string;
  action: 'add' | 'remove';
  error?: string;
}

export interface ChatResponse {
  message: string;
  trades?: ExecutedTrade[];
  watchlist_changes?: WatchlistChange[];
}

export type ConnectionStatus = 'connected' | 'reconnecting' | 'disconnected';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  trades?: ExecutedTrade[];
  watchlist_changes?: WatchlistChange[];
  pending?: boolean;
}
