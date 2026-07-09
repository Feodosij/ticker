export function formatCurrency(value: number, opts: { sign?: boolean } = {}): string {
  const sign = opts.sign && value > 0 ? '+' : '';
  return (
    sign +
    value.toLocaleString('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })
  );
}

export function formatPrice(value: number): string {
  return value.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function formatPct(value: number): string {
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

export function formatQty(value: number): string {
  const rounded = Math.round(value * 1e6) / 1e6;
  return Number.isInteger(rounded)
    ? rounded.toString()
    : rounded.toLocaleString('en-US', { maximumFractionDigits: 4 });
}

export function pnlColor(value: number): string {
  if (value > 0) return 'text-up';
  if (value < 0) return 'text-down';
  return 'text-muted';
}
