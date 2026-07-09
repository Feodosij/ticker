import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import PriceCell from './PriceCell';

describe('PriceCell', () => {
  it('renders the formatted price', () => {
    render(<PriceCell price={190.5} />);
    expect(screen.getByText('190.50')).toBeInTheDocument();
  });

  it('does not flash on first render', () => {
    render(<PriceCell price={100} />);
    const cell = screen.getByText('100.00');
    expect(cell).toHaveAttribute('data-flash', '');
    expect(cell.className).not.toMatch(/animate-flash/);
  });

  it('flashes green when the price ticks up', () => {
    const { rerender } = render(<PriceCell price={100} />);
    rerender(<PriceCell price={101} />);
    const cell = screen.getByText('101.00');
    expect(cell).toHaveAttribute('data-flash', 'up');
    expect(cell.className).toMatch(/animate-flash-up/);
  });

  it('flashes red when the price ticks down', () => {
    const { rerender } = render(<PriceCell price={100} />);
    rerender(<PriceCell price={99} />);
    const cell = screen.getByText('99.00');
    expect(cell).toHaveAttribute('data-flash', 'down');
    expect(cell.className).toMatch(/animate-flash-down/);
  });

  it('does not flash when the price is unchanged', () => {
    const { rerender } = render(<PriceCell price={100} />);
    rerender(<PriceCell price={100} />);
    const cell = screen.getByText('100.00');
    expect(cell).toHaveAttribute('data-flash', '');
  });
});
