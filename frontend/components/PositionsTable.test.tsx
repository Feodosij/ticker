import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { makeAppState, priceUpdate } from '@/test/appState';
import type { ApiPortfolio } from '@/lib/types';
import PositionsTable from './PositionsTable';

const mockStore = { current: makeAppState() };
vi.mock('@/lib/store', () => ({
  useApp: () => mockStore.current,
}));

const portfolio: ApiPortfolio = {
  cash_balance: 5000,
  total_value: 6000,
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
  ],
};

beforeEach(() => {
  mockStore.current = makeAppState();
});

describe('PositionsTable', () => {
  it('shows an empty state with no positions', () => {
    mockStore.current = makeAppState({ portfolio });
    // strip positions
    mockStore.current.portfolio = { ...portfolio, positions: [] };
    render(<PositionsTable />);
    expect(screen.getByText(/No open positions/i)).toBeInTheDocument();
  });

  it('displays a position with live-computed P&L', () => {
    mockStore.current = makeAppState({
      portfolio,
      prices: { AAPL: priceUpdate('AAPL', 115) }, // +$15/sh => +$150 (+15%)
    });
    render(<PositionsTable />);
    const row = screen.getByText('AAPL').closest('tr')!;
    const cells = within(row);
    expect(cells.getByText('10')).toBeInTheDocument(); // qty
    expect(cells.getByText('115.00')).toBeInTheDocument(); // current price
    expect(cells.getByText('$1,150.00')).toBeInTheDocument(); // market value
    expect(cells.getByText('+$150.00')).toBeInTheDocument(); // unrealized P&L
    expect(cells.getByText('+15.00%')).toBeInTheDocument();
  });
});
