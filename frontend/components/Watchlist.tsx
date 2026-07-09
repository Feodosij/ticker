'use client';

import { useState } from 'react';
import { useApp } from '@/lib/store';
import { formatPct, pnlColor } from '@/lib/format';
import Panel from './Panel';
import PriceCell from './PriceCell';
import Sparkline from './Sparkline';

export default function Watchlist() {
  const {
    watchlist,
    prices,
    sparklines,
    selectedTicker,
    selectTicker,
    addTicker,
    removeTicker,
  } = useApp();
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!draft.trim()) return;
    setBusy(true);
    const ok = await addTicker(draft);
    setBusy(false);
    if (ok) setDraft('');
  };

  return (
    <Panel
      title="Watchlist"
      right={
        <form onSubmit={submit} className="flex items-center gap-1">
          <input
            aria-label="Add ticker"
            value={draft}
            onChange={(e) => setDraft(e.target.value.toUpperCase())}
            placeholder="ADD"
            maxLength={8}
            className="w-16 rounded border border-border bg-bg-base px-1.5 py-0.5 font-mono text-xs uppercase tracking-wide text-slate-100 placeholder:text-faint focus:border-primary focus:outline-none"
          />
          <button
            type="submit"
            disabled={busy || !draft.trim()}
            className="rounded border border-border-strong px-1.5 py-0.5 text-xs text-muted transition-colors hover:border-primary hover:text-primary disabled:opacity-40"
          >
            +
          </button>
        </form>
      }
    >
      <table className="w-full border-collapse text-sm">
        <thead className="sticky top-0 z-10 bg-bg-panel">
          <tr className="text-[10px] uppercase tracking-wide text-faint">
            <th className="px-3 py-1.5 text-left font-medium">Ticker</th>
            <th className="px-2 py-1.5 text-right font-medium">Last</th>
            <th className="px-2 py-1.5 text-right font-medium">Chg%</th>
            <th className="px-2 py-1.5 text-center font-medium">Trend</th>
            <th className="w-6" />
          </tr>
        </thead>
        <tbody>
          {watchlist.length === 0 && (
            <tr>
              <td colSpan={5} className="px-3 py-6 text-center text-xs text-faint">
                No tickers yet. Add one above.
              </td>
            </tr>
          )}
          {watchlist.map((item) => {
            const live = prices[item.ticker];
            const price = live?.price ?? item.price;
            const changePct = live?.change_pct ?? item.change_pct;
            const selected = selectedTicker === item.ticker;
            const hasPrice = price != null;
            const hasChange = changePct != null;
            return (
              <tr
                key={item.ticker}
                onClick={() => selectTicker(item.ticker)}
                className={`group cursor-pointer border-t border-border/60 transition-colors ${
                  selected ? 'bg-primary/10' : 'hover:bg-bg-raised'
                }`}
              >
                <td className="px-3 py-1.5 text-left">
                  <span className="flex items-center gap-1.5 font-mono text-[13px] font-semibold text-slate-100">
                    {selected && <span className="h-3 w-0.5 rounded bg-primary" />}
                    {item.ticker}
                  </span>
                </td>
                <td className="px-2 py-1.5 text-right font-mono text-slate-100">
                  {hasPrice ? <PriceCell price={price} /> : <span className="text-faint">—</span>}
                </td>
                <td
                  className={`px-2 py-1.5 text-right font-mono ${
                    hasChange ? pnlColor(changePct) : 'text-faint'
                  }`}
                >
                  {hasChange ? formatPct(changePct) : '—'}
                </td>
                <td className="px-2 py-1.5">
                  <div className="flex justify-center">
                    <Sparkline data={sparklines[item.ticker] ?? []} />
                  </div>
                </td>
                <td className="pr-2">
                  <button
                    aria-label={`Remove ${item.ticker}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      removeTicker(item.ticker);
                    }}
                    className="text-faint opacity-0 transition-opacity hover:text-down group-hover:opacity-100"
                  >
                    ×
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Panel>
  );
}
