'use client';

import { ResponsiveContainer, Treemap } from 'recharts';
import { useApp } from '@/lib/store';
import { deriveLivePortfolio } from '@/lib/portfolio';
import { formatPct } from '@/lib/format';
import Panel from './Panel';

interface Node {
  name: string;
  size: number;
  pnlPct: number;
}

// Map P&L% to a green/red fill; magnitude saturates around +/-5%.
function fillFor(pnlPct: number): string {
  const mag = Math.min(Math.abs(pnlPct) / 5, 1);
  const alpha = 0.2 + mag * 0.6;
  const rgb = pnlPct >= 0 ? '38,161,123' : '224,75,90';
  return `rgba(${rgb},${alpha})`;
}

function TreemapCell(props: any) {
  const { x, y, width, height, name, pnlPct } = props;
  if (width <= 0 || height <= 0) return null;
  const showLabel = width > 46 && height > 26;
  const showPct = width > 46 && height > 42;
  return (
    <g>
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        style={{ fill: fillFor(pnlPct ?? 0), stroke: '#0d1117', strokeWidth: 2 }}
      />
      {showLabel && (
        <text
          x={x + 6}
          y={y + 16}
          fill="#e6ecf5"
          fontSize={12}
          fontWeight={700}
          fontFamily="var(--font-mono)"
        >
          {name}
        </text>
      )}
      {showPct && (
        <text x={x + 6} y={y + 32} fill="#c9d3e0" fontSize={11} fontFamily="var(--font-mono)">
          {formatPct(pnlPct ?? 0)}
        </text>
      )}
    </g>
  );
}

export default function Heatmap() {
  const { portfolio, prices } = useApp();
  const live = deriveLivePortfolio(portfolio, prices);
  const positions = live?.positions ?? [];

  const data: Node[] = positions
    .filter((p) => p.quantity > 0)
    .map((p) => ({
      name: p.ticker,
      size: Math.max(p.market_value, 0.01),
      pnlPct: p.pnl_pct,
    }));

  return (
    <Panel title="Portfolio Heatmap" bodyClassName="p-1.5">
      {data.length === 0 ? (
        <div className="flex h-full items-center justify-center text-xs text-faint">
          No positions yet
        </div>
      ) : (
        <ResponsiveContainer width="100%" height="100%">
          <Treemap
            data={data}
            dataKey="size"
            nameKey="name"
            isAnimationActive={false}
            content={<TreemapCell />}
          />
        </ResponsiveContainer>
      )}
    </Panel>
  );
}
