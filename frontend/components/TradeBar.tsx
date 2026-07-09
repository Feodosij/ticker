'use client';

import { useEffect, useState } from 'react';
import { useApp } from '@/lib/store';
import { formatCurrency } from '@/lib/format';
import type { TradeSide } from '@/lib/types';

export default function TradeBar() {
  const { selectedTicker, prices, executeTrade, actionError, clearActionError } = useApp();
  const [ticker, setTicker] = useState('');
  const [qty, setQty] = useState('');
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  // Follow the selected ticker until the user types their own.
  const [touched, setTouched] = useState(false);
  useEffect(() => {
    if (!touched && selectedTicker) setTicker(selectedTicker);
  }, [selectedTicker, touched]);

  const symbol = ticker.trim().toUpperCase();
  const price = prices[symbol]?.price;
  const quantity = Number(qty);
  const estimate = price && quantity > 0 ? price * quantity : null;
  const valid = symbol.length > 0 && quantity > 0;

  const doTrade = async (side: TradeSide) => {
    if (!valid) return;
    setBusy(true);
    setToast(null);
    const ok = await executeTrade({ ticker: symbol, quantity, side });
    setBusy(false);
    if (ok) {
      setToast(`${side === 'buy' ? 'Bought' : 'Sold'} ${quantity} ${symbol}`);
      setQty('');
      setTimeout(() => setToast(null), 3000);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2 border-t border-border bg-bg-deep px-3 py-2">
      <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-faint">
        Trade
      </span>

      <input
        aria-label="Trade ticker"
        value={ticker}
        onChange={(e) => {
          setTouched(true);
          setTicker(e.target.value.toUpperCase());
          clearActionError();
        }}
        placeholder="TICKER"
        maxLength={8}
        className="w-24 rounded border border-border bg-bg-base px-2 py-1.5 font-mono text-sm uppercase tracking-wide text-slate-100 placeholder:text-faint focus:border-primary focus:outline-none"
      />

      <input
        aria-label="Trade quantity"
        value={qty}
        onChange={(e) => {
          setQty(e.target.value.replace(/[^0-9.]/g, ''));
          clearActionError();
        }}
        inputMode="decimal"
        placeholder="QTY"
        className="w-24 rounded border border-border bg-bg-base px-2 py-1.5 font-mono text-sm text-slate-100 placeholder:text-faint focus:border-primary focus:outline-none"
      />

      <div className="tabular min-w-[104px] font-mono text-xs text-muted">
        {price != null ? (
          <>
            <span className="text-faint">@</span> {formatCurrency(price)}
          </>
        ) : (
          <span className="text-faint">no live price</span>
        )}
        {estimate != null && (
          <span className="ml-2 text-slate-300">≈ {formatCurrency(estimate)}</span>
        )}
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={() => doTrade('buy')}
          disabled={!valid || busy}
          className="rounded bg-secondary px-4 py-1.5 text-sm font-semibold text-white transition-colors hover:bg-secondary/85 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Buy
        </button>
        <button
          onClick={() => doTrade('sell')}
          disabled={!valid || busy}
          className="rounded border border-down/70 px-4 py-1.5 text-sm font-semibold text-down transition-colors hover:bg-down/10 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Sell
        </button>
      </div>

      {actionError && (
        <span role="alert" className="text-xs text-down">
          {actionError}
        </span>
      )}
      {toast && !actionError && (
        <span role="status" className="text-xs text-up">
          {toast}
        </span>
      )}
    </div>
  );
}
