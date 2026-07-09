import { describe, expect, it } from 'vitest';
import { deriveLivePortfolio } from './portfolio';
import { formatCurrency, formatPct, formatQty, pnlColor } from './format';
import type { ApiPortfolio } from './types';
import { priceUpdate } from '@/test/appState';

const basePortfolio: ApiPortfolio = {
  cash_balance: 5000,
  total_value: 7000,
  total_unrealized_pnl: 0,
  positions: [
    {
      ticker: 'AAPL',
      quantity: 10,
      avg_cost: 100,
      current_price: 100,
      unrealized_pnl: 0,
      unrealized_pnl_pct: 0,
    },
    {
      ticker: 'TSLA',
      quantity: 4,
      avg_cost: 250,
      current_price: 250,
      unrealized_pnl: 0,
      unrealized_pnl_pct: 0,
    },
  ],
};

describe('deriveLivePortfolio', () => {
  it('returns null when portfolio is null', () => {
    expect(deriveLivePortfolio(null, {})).toBeNull();
  });

  it('overlays live prices onto positions and recomputes P&L', () => {
    const prices = {
      AAPL: priceUpdate('AAPL', 110), // +$10/sh over avg 100 => +$100 (+10%)
      TSLA: priceUpdate('TSLA', 200), // -$50/sh over avg 250 => -$200 (-20%)
    };
    const live = deriveLivePortfolio(basePortfolio, prices)!;

    const aapl = live.positions.find((p) => p.ticker === 'AAPL')!;
    expect(aapl.current_price).toBe(110);
    expect(aapl.market_value).toBe(1100);
    expect(aapl.unrealized_pnl).toBe(100);
    expect(aapl.pnl_pct).toBeCloseTo(10);

    const tsla = live.positions.find((p) => p.ticker === 'TSLA')!;
    expect(tsla.unrealized_pnl).toBe(-200);
    expect(tsla.pnl_pct).toBeCloseTo(-20);

    // Aggregates: positions 1100 + 800 = 1900; total = cash 5000 + 1900
    expect(live.positions_value).toBe(1900);
    expect(live.unrealized_pnl).toBe(-100);
    expect(live.total_value).toBe(6900);
  });

  it('falls back to the last server price when no live tick exists', () => {
    const live = deriveLivePortfolio(basePortfolio, {})!;
    const aapl = live.positions.find((p) => p.ticker === 'AAPL')!;
    expect(aapl.current_price).toBe(100);
    expect(live.total_value).toBe(7000);
  });
});

describe('formatters', () => {
  it('formats currency and signed values', () => {
    expect(formatCurrency(1234.5)).toBe('$1,234.50');
    expect(formatCurrency(100, { sign: true })).toBe('+$100.00');
    expect(formatCurrency(-100, { sign: true })).toBe('-$100.00');
  });

  it('formats percentages with sign', () => {
    expect(formatPct(2.5)).toBe('+2.50%');
    expect(formatPct(-1.2)).toBe('-1.20%');
  });

  it('formats fractional and whole quantities', () => {
    expect(formatQty(10)).toBe('10');
    expect(formatQty(2.5)).toBe('2.5');
  });

  it('maps P&L sign to a color class', () => {
    expect(pnlColor(5)).toBe('text-up');
    expect(pnlColor(-5)).toBe('text-down');
    expect(pnlColor(0)).toBe('text-muted');
  });
});
