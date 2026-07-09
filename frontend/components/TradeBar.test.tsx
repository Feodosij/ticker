import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { makeAppState, priceUpdate } from '@/test/appState';
import TradeBar from './TradeBar';

const mockStore = { current: makeAppState() };
vi.mock('@/lib/store', () => ({
  useApp: () => mockStore.current,
}));

beforeEach(() => {
  mockStore.current = makeAppState({
    selectedTicker: 'AAPL',
    prices: { AAPL: priceUpdate('AAPL', 200) },
  });
});

describe('TradeBar', () => {
  it('prefills the ticker from the current selection', () => {
    render(<TradeBar />);
    expect((screen.getByLabelText('Trade ticker') as HTMLInputElement).value).toBe('AAPL');
  });

  it('shows an estimated cost from the live price and quantity', async () => {
    const user = userEvent.setup();
    render(<TradeBar />);
    await user.type(screen.getByLabelText('Trade quantity'), '3');
    expect(screen.getByText(/≈ \$600\.00/)).toBeInTheDocument();
  });

  it('submits a buy order with the entered quantity', async () => {
    const user = userEvent.setup();
    render(<TradeBar />);
    await user.type(screen.getByLabelText('Trade quantity'), '2');
    await user.click(screen.getByRole('button', { name: 'Buy' }));
    expect(mockStore.current.executeTrade).toHaveBeenCalledWith({
      ticker: 'AAPL',
      quantity: 2,
      side: 'buy',
    });
  });

  it('submits a sell order', async () => {
    const user = userEvent.setup();
    render(<TradeBar />);
    await user.type(screen.getByLabelText('Trade quantity'), '1');
    await user.click(screen.getByRole('button', { name: 'Sell' }));
    expect(mockStore.current.executeTrade).toHaveBeenCalledWith({
      ticker: 'AAPL',
      quantity: 1,
      side: 'sell',
    });
  });

  it('keeps trade buttons disabled until quantity is valid', async () => {
    render(<TradeBar />);
    expect(screen.getByRole('button', { name: 'Buy' })).toBeDisabled();
  });

  it('surfaces an action error from the store', () => {
    mockStore.current = makeAppState({
      selectedTicker: 'AAPL',
      prices: { AAPL: priceUpdate('AAPL', 200) },
      actionError: 'Insufficient cash',
    });
    render(<TradeBar />);
    expect(screen.getByRole('alert')).toHaveTextContent('Insufficient cash');
  });
});
