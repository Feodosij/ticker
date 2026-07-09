import type { ApiPortfolio, LivePortfolio, LivePosition, PriceUpdate } from './types';

/**
 * Overlays the live SSE price feed onto the last-fetched portfolio so P&L,
 * market value and total value tick between the 30s server refreshes.
 * The server remains the source of truth for cash and quantities.
 */
export function deriveLivePortfolio(
  portfolio: ApiPortfolio | null,
  prices: Record<string, PriceUpdate>,
): LivePortfolio | null {
  if (!portfolio) return null;

  let positionsValue = 0;
  let unrealized = 0;

  const positions: LivePosition[] = portfolio.positions.map((p) => {
    const live = prices[p.ticker]?.price;
    const current = typeof live === 'number' ? live : p.current_price;
    const marketValue = current * p.quantity;
    const costBasis = p.avg_cost * p.quantity;
    const pnl = marketValue - costBasis;
    positionsValue += marketValue;
    unrealized += pnl;
    return {
      ...p,
      current_price: current,
      market_value: marketValue,
      unrealized_pnl: pnl,
      pnl_pct: costBasis > 0 ? (pnl / costBasis) * 100 : 0,
    };
  });

  return {
    ...portfolio,
    positions,
    positions_value: positionsValue,
    unrealized_pnl: unrealized,
    total_value: portfolio.cash_balance + positionsValue,
  };
}
