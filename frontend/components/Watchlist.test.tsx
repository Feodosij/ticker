import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { makeAppState, priceUpdate } from '@/test/appState';
import Watchlist from './Watchlist';

const mockStore = { current: makeAppState() };
vi.mock('@/lib/store', () => ({
  useApp: () => mockStore.current,
}));

describe('Watchlist', () => {
  beforeEach(() => {
    mockStore.current = makeAppState({
      watchlist: [
        { ticker: 'AAPL', price: 190, change_pct: 1.2 },
        { ticker: 'TSLA', price: 250, change_pct: -0.8 },
      ],
      prices: {
        AAPL: priceUpdate('AAPL', 191.25, 1.5),
        TSLA: priceUpdate('TSLA', 248, -0.8),
      },
      sparklines: { AAPL: [190, 190.5, 191.25] },
      selectedTicker: 'AAPL',
    });
  });

  it('renders each watchlist ticker with its live price and change', () => {
    render(<Watchlist />);
    expect(screen.getByText('AAPL')).toBeInTheDocument();
    expect(screen.getByText('TSLA')).toBeInTheDocument();
    // Live SSE price wins over the seeded watchlist price.
    expect(screen.getByText('191.25')).toBeInTheDocument();
    expect(screen.getByText('+1.50%')).toBeInTheDocument();
    expect(screen.getByText('-0.80%')).toBeInTheDocument();
  });

  it('selects a ticker when its row is clicked', async () => {
    const user = userEvent.setup();
    render(<Watchlist />);
    await user.click(screen.getByText('TSLA'));
    expect(mockStore.current.selectTicker).toHaveBeenCalledWith('TSLA');
  });

  it('adds a ticker through the input form', async () => {
    const user = userEvent.setup();
    render(<Watchlist />);
    await user.type(screen.getByLabelText('Add ticker'), 'nvda');
    await user.click(screen.getByRole('button', { name: '+' }));
    expect(mockStore.current.addTicker).toHaveBeenCalledWith('NVDA');
  });

  it('removes a ticker via its remove button', async () => {
    const user = userEvent.setup();
    render(<Watchlist />);
    await user.click(screen.getByLabelText('Remove TSLA'));
    expect(mockStore.current.removeTicker).toHaveBeenCalledWith('TSLA');
  });

  it('shows an empty state when there are no tickers', () => {
    mockStore.current = makeAppState({ watchlist: [] });
    render(<Watchlist />);
    expect(screen.getByText(/No tickers yet/i)).toBeInTheDocument();
  });
});
