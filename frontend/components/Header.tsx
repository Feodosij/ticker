'use client';

import { useApp } from '@/lib/store';
import { deriveLivePortfolio } from '@/lib/portfolio';
import { formatCurrency, formatPct, pnlColor } from '@/lib/format';
import StatusDot from './StatusDot';

export default function Header({ onToggleChat }: { onToggleChat: () => void }) {
  const { portfolio, prices, status } = useApp();
  const live = deriveLivePortfolio(portfolio, prices);

  const totalValue = live?.total_value ?? 0;
  const cash = live?.cash_balance ?? 0;
  const pnl = live?.unrealized_pnl ?? 0;
  const pnlPct = live && live.positions_value - pnl !== 0
    ? (pnl / (live.positions_value - pnl)) * 100
    : 0;

  return (
    <header className="flex items-center justify-between gap-4 border-b border-border bg-bg-deep px-4 py-2.5">
      <div className="flex items-center gap-3">
        <div className="flex items-baseline gap-1.5">
          <span className="font-mono text-lg font-bold tracking-tight text-accent">Ticker</span>
        </div>
        <span className="hidden text-[10px] uppercase tracking-[0.2em] text-faint sm:inline">
          Trading Workstation
        </span>
      </div>

      <div className="flex items-center gap-4 sm:gap-7">
        <Metric label="Portfolio Value">
          <span className="tabular text-base font-semibold text-primary sm:text-lg">
            {formatCurrency(totalValue)}
          </span>
        </Metric>
        <Metric label="Unrealized P&L">
          <span className={`tabular text-sm font-semibold sm:text-base ${pnlColor(pnl)}`}>
            {formatCurrency(pnl, { sign: true })}
            <span className="ml-1 text-xs opacity-80">{formatPct(pnlPct)}</span>
          </span>
        </Metric>
        <Metric label="Cash">
          <span className="tabular text-sm font-semibold text-slate-200 sm:text-base">
            {formatCurrency(cash)}
          </span>
        </Metric>

        <StatusDot status={status} />

        <button
          onClick={onToggleChat}
          className="rounded border border-border-strong bg-bg-raised px-2.5 py-1.5 text-xs font-medium text-slate-200 transition-colors hover:border-primary hover:text-primary lg:hidden"
        >
          Chat
        </button>
      </div>
    </header>
  );
}

function Metric({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col items-end leading-tight">
      <span className="text-[9px] uppercase tracking-[0.14em] text-faint">{label}</span>
      {children}
    </div>
  );
}
