'use client';

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
import { formatCurrency } from '@/lib/format';
import Panel from './Panel';

export default function PnLChart() {
  const { history } = useApp();

  const data = history.map((s) => ({
    t: new Date(s.recorded_at).getTime(),
    value: s.total_value,
  }));

  const first = data[0]?.value ?? 0;
  const last = data[data.length - 1]?.value ?? 0;
  const rising = last >= first;
  const stroke = rising ? '#26a17b' : '#e04b5a';

  return (
    <Panel title="Portfolio Value" bodyClassName="p-2">
      {data.length < 2 ? (
        <div className="flex h-full items-center justify-center text-xs text-faint">
          Accruing value history…
        </div>
      ) : (
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="pnlFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={stroke} stopOpacity={0.25} />
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
                  hour: '2-digit',
                  minute: '2-digit',
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
              width={60}
              tickFormatter={(v) => `$${Math.round(v / 1000)}k`}
            />
            <Tooltip
              contentStyle={{
                background: '#0a0e16',
                border: '1px solid #30394d',
                borderRadius: 6,
                fontSize: 12,
              }}
              labelStyle={{ color: '#7d8697' }}
              labelFormatter={(t) => new Date(Number(t)).toLocaleString('en-US')}
              formatter={(v: number) => [formatCurrency(v), 'Total']}
            />
            <Area
              type="monotone"
              dataKey="value"
              stroke={stroke}
              strokeWidth={1.6}
              fill="url(#pnlFill)"
              isAnimationActive={false}
              dot={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </Panel>
  );
}
