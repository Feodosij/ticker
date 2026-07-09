'use client';

interface Props {
  data: number[];
  width?: number;
  height?: number;
}

/**
 * Tiny inline SVG sparkline built from the in-memory price series. Kept as raw
 * SVG (not Recharts) so it stays cheap when rendered once per watchlist row.
 */
export default function Sparkline({ data, width = 88, height = 26 }: Props) {
  if (!data || data.length < 2) {
    return (
      <svg width={width} height={height} aria-hidden className="opacity-40">
        <line
          x1={0}
          y1={height / 2}
          x2={width}
          y2={height / 2}
          stroke="#30394d"
          strokeDasharray="2 3"
          strokeWidth={1}
        />
      </svg>
    );
  }

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const stepX = width / (data.length - 1);
  const pad = 2;
  const usable = height - pad * 2;

  const points = data.map((v, i) => {
    const x = i * stepX;
    const y = pad + (1 - (v - min) / range) * usable;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  const rising = data[data.length - 1] >= data[0];
  const stroke = rising ? '#26a17b' : '#e04b5a';

  return (
    <svg width={width} height={height} aria-label="price sparkline" role="img">
      <polyline
        points={points.join(' ')}
        fill="none"
        stroke={stroke}
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}
