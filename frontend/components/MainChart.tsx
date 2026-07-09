'use client';

import { useEffect, useRef, useState } from 'react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { useApp } from '@/lib/store';
import { formatPct, formatPrice, pnlColor } from '@/lib/format';
import Panel from './Panel';

interface Point {
  t: number;
  price: number;
}

const MAX_POINTS = 240;

export default function MainChart() {
  const { selectedTicker, prices } = useApp();
  const [series, setSeries] = useState<Point[]>([]);
  const activeTicker = useRef<string | null>(null);

  const live = selectedTicker ? prices[selectedTicker] : undefined;
  const price = live?.price;

  // Reset the buffer when the selected ticker changes.
  useEffect(() => {
    if (activeTicker.current !== selectedTicker) {
      activeTicker.current = selectedTicker;
      setSeries([]);
    }
  }, [selectedTicker]);

  // Append each new tick for the selected ticker.
  useEffect(() => {
    if (price == null) return;
    setSeries((prev) => {
      const next = [...prev, { t: Date.now(), price }];
      if (next.length > MAX_POINTS) next.shift();
      return next;
    });
  }, [price]);

  const changePct = live?.change_pct ?? 0;
  const rising = changePct >= 0;
  const stroke = rising ? '#26a17b' : '#e04b5a';

  return (
    <Panel
      title="Chart"
      right={
        selectedTicker ? (
          <div className="flex items-center gap-3">
            <span className="font-mono text-sm font-bold text-slate-100">{selectedTicker}</span>
            {price != null && (
              <span className="tabular font-mono text-sm text-slate-100">
                {formatPrice(price)}
              </span>
            )}
            <span className={`tabular font-mono text-xs ${pnlColor(changePct)}`}>
              {formatPct(changePct)}
            </span>
          </div>
        ) : null
      }
      bodyClassName="p-2"
    >
      {!selectedTicker ? (
        <Empty label="Select a ticker from the watchlist" />
      ) : series.length < 2 ? (
        <Empty label={`Waiting for ${selectedTicker} price stream…`} />
      ) : (
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={series} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="mainFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={stroke} stopOpacity={0.28} />
                <stop offset="100%" stopColor={stroke} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#232b3a" strokeDasharray="2 4" vertical={false} />
            <XAxis
              dataKey="t"
              type="number"
              domain={['dataMin', 'dataMax']}
              scale="time"
              tickFormatter={(t) =>
                new Date(t).toLocaleTimeString('en-US', {
                  hour12: false,
                  minute: '2-digit',
                  second: '2-digit',
                })
              }
              tick={{ fill: '#5a6272', fontSize: 10 }}
              stroke="#232b3a"
              minTickGap={48}
            />
            <YAxis
              orientation="right"
              domain={['auto', 'auto']}
              tick={{ fill: '#5a6272', fontSize: 10 }}
              stroke="#232b3a"
              width={52}
              tickFormatter={(v) => formatPrice(v)}
            />
            <Tooltip
              contentStyle={{
                background: '#0a0e16',
                border: '1px solid #30394d',
                borderRadius: 6,
                fontSize: 12,
              }}
              labelStyle={{ color: '#7d8697' }}
              labelFormatter={(t) => new Date(Number(t)).toLocaleTimeString('en-US')}
              formatter={(v: number) => [formatPrice(v), 'Price']}
            />
            <Area
              type="monotone"
              dataKey="price"
              stroke={stroke}
              strokeWidth={1.6}
              fill="url(#mainFill)"
              isAnimationActive={false}
              dot={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </Panel>
  );
}

function Empty({ label }: { label: string }) {
  return (
    <div className="flex h-full items-center justify-center text-xs text-faint">{label}</div>
  );
}
