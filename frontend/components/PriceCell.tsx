'use client';

import { useEffect, useRef, useState } from 'react';
import { formatPrice } from '@/lib/format';

interface Props {
  price: number;
  className?: string;
}

/**
 * Shows a price and briefly flashes its background green/red when the value
 * changes (PLAN.md §10). The flash is keyed by a nonce so the CSS animation
 * restarts on every tick; it self-clears after the animation window.
 */
export default function PriceCell({ price, className = '' }: Props) {
  const prev = useRef<number | null>(null);
  const [flash, setFlash] = useState<{ dir: 'up' | 'down'; nonce: number } | null>(null);

  useEffect(() => {
    if (prev.current !== null && price !== prev.current) {
      const dir = price > prev.current ? 'up' : 'down';
      setFlash((f) => ({ dir, nonce: (f?.nonce ?? 0) + 1 }));
    }
    prev.current = price;
  }, [price]);

  useEffect(() => {
    if (!flash) return;
    const id = setTimeout(() => setFlash(null), 600);
    return () => clearTimeout(id);
  }, [flash]);

  const flashClass = flash
    ? flash.dir === 'up'
      ? 'animate-flash-up'
      : 'animate-flash-down'
    : '';

  return (
    <span
      key={flash?.nonce ?? 'static'}
      data-flash={flash?.dir ?? ''}
      className={`tabular inline-block rounded px-1 ${flashClass} ${className}`}
    >
      {formatPrice(price)}
    </span>
  );
}
