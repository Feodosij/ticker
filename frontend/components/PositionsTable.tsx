'use client';

import { useApp } from '@/lib/store';
import { deriveLivePortfolio } from '@/lib/portfolio';
import { formatCurrency, formatPct, formatPrice, formatQty, pnlColor } from '@/lib/format';
import Panel from './Panel';

export default function PositionsTable() {
  const { portfolio, prices, selectTicker, selectedTicker } = useApp();
  const live = deriveLivePortfolio(portfolio, prices);
  const positions = (live?.positions ?? []).filter((p) => p.quantity > 0);

  return (
    <Panel title="Positions">
      <table className="w-full border-collapse text-sm">
        <thead className="sticky top-0 z-10 bg-bg-panel text-[10px] uppercase tracking-wide text-faint">
          <tr>
            <th className="px-3 py-1.5 text-left font-medium">Ticker</th>
            <th className="px-2 py-1.5 text-right font-medium">Qty</th>
            <th className="px-2 py-1.5 text-right font-medium">Avg</th>
            <th className="px-2 py-1.5 text-right font-medium">Last</th>
            <th className="px-2 py-1.5 text-right font-medium">Value</th>
            <th className="px-2 py-1.5 text-right font-medium">P&L</th>
            <th className="px-3 py-1.5 text-right font-medium">%</th>
          </tr>
        </thead>
        <tbody>
          {positions.length === 0 && (
            <tr>
              <td colSpan={7} className="px-3 py-6 text-center text-xs text-faint">
                No open positions. Use the trade bar below to buy.
              </td>
            </tr>
          )}
          {positions.map((p) => (
            <tr
              key={p.ticker}
              onClick={() => selectTicker(p.ticker)}
              className={`cursor-pointer border-t border-border/60 font-mono transition-colors ${
                selectedTicker === p.ticker ? 'bg-primary/10' : 'hover:bg-bg-raised'
              }`}
            >
              <td className="px-3 py-1.5 text-left font-semibold text-slate-100">{p.ticker}</td>
              <td className="tabular px-2 py-1.5 text-right text-slate-300">
                {formatQty(p.quantity)}
              </td>
              <td className="tabular px-2 py-1.5 text-right text-slate-300">
                {formatPrice(p.avg_cost)}
              </td>
              <td className="tabular px-2 py-1.5 text-right text-slate-100">
                {formatPrice(p.current_price)}
              </td>
              <td className="tabular px-2 py-1.5 text-right text-slate-100">
                {formatCurrency(p.market_value)}
              </td>
              <td className={`tabular px-2 py-1.5 text-right ${pnlColor(p.unrealized_pnl)}`}>
                {formatCurrency(p.unrealized_pnl, { sign: true })}
              </td>
              <td className={`tabular px-3 py-1.5 text-right ${pnlColor(p.pnl_pct)}`}>
                {formatPct(p.pnl_pct)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}
