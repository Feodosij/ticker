import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { makeAppState } from '@/test/appState';
import ChatPanel from './ChatPanel';

const mockStore = { current: makeAppState() };
vi.mock('@/lib/store', () => ({
  useApp: () => mockStore.current,
}));

// jsdom lacks scrollTo on elements; stub it for the auto-scroll effect.
beforeEach(() => {
  Element.prototype.scrollTo = vi.fn();
  mockStore.current = makeAppState();
});

describe('ChatPanel', () => {
  it('shows the empty-state prompt when there are no messages', () => {
    render(<ChatPanel open onClose={() => {}} />);
    expect(screen.getByText(/Ask Ticker to analyze or trade/i)).toBeInTheDocument();
  });

  it('renders user and assistant messages', () => {
    mockStore.current = makeAppState({
      chatMessages: [
        { id: '1', role: 'user', content: 'How is my portfolio?' },
        { id: '2', role: 'assistant', content: 'You are 60% in tech.' },
      ],
    });
    render(<ChatPanel open onClose={() => {}} />);
    expect(screen.getByText('How is my portfolio?')).toBeInTheDocument();
    expect(screen.getByText('You are 60% in tech.')).toBeInTheDocument();
  });

  it('shows a typing indicator while a response is pending', () => {
    mockStore.current = makeAppState({
      chatMessages: [{ id: '1', role: 'assistant', content: '', pending: true }],
      chatLoading: true,
    });
    render(<ChatPanel open onClose={() => {}} />);
    expect(screen.getByLabelText('Assistant is typing')).toBeInTheDocument();
  });

  it('renders inline trade and watchlist confirmations', () => {
    mockStore.current = makeAppState({
      chatMessages: [
        {
          id: '1',
          role: 'assistant',
          content: 'Done.',
          trades: [{ ticker: 'NVDA', side: 'buy', quantity: 5, price: 120 }],
          watchlist_changes: [{ ticker: 'PYPL', action: 'add' }],
        },
      ],
    });
    render(<ChatPanel open onClose={() => {}} />);
    expect(screen.getByText(/Bought 5 NVDA @ 120.00/)).toBeInTheDocument();
    expect(screen.getByText(/Added PYPL to watchlist/)).toBeInTheDocument();
  });

  it('renders a failed trade with its error', () => {
    mockStore.current = makeAppState({
      chatMessages: [
        {
          id: '1',
          role: 'assistant',
          content: 'Could not complete that.',
          trades: [
            { ticker: 'AAPL', side: 'buy', quantity: 100, price: 190, error: 'insufficient cash' },
          ],
        },
      ],
    });
    render(<ChatPanel open onClose={() => {}} />);
    expect(screen.getByText(/BUY 100 AAPL failed: insufficient cash/)).toBeInTheDocument();
  });

  it('sends a message on submit and clears the input', async () => {
    const user = userEvent.setup();
    render(<ChatPanel open onClose={() => {}} />);
    const input = screen.getByLabelText('Message Ticker') as HTMLTextAreaElement;
    await user.type(input, 'buy 3 AAPL');
    await user.click(screen.getByRole('button', { name: 'Send' }));
    expect(mockStore.current.sendChat).toHaveBeenCalledWith('buy 3 AAPL');
    expect(input.value).toBe('');
  });

  it('disables the send button while loading', () => {
    mockStore.current = makeAppState({ chatLoading: true });
    render(<ChatPanel open onClose={() => {}} />);
    expect(screen.getByRole('button', { name: 'Send' })).toBeDisabled();
  });
});
