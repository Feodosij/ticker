'use client';

import { useEffect, useRef, useState } from 'react';
import { PRICE_STREAM_URL } from './api';
import type { ConnectionStatus, PriceUpdate } from './types';

export interface PriceStreamState {
  prices: Record<string, PriceUpdate>;
  sparklines: Record<string, number[]>;
  status: ConnectionStatus;
}

const MAX_SPARK_POINTS = 60;

/**
 * Subscribes to the SSE price feed. Sparkline series are accumulated purely in
 * memory since page load — a refresh resets them by design (PLAN.md §10).
 * EventSource retries automatically; we surface that as a "reconnecting" status.
 */
export function usePriceStream(): PriceStreamState {
  const [prices, setPrices] = useState<Record<string, PriceUpdate>>({});
  const [sparklines, setSparklines] = useState<Record<string, number[]>>({});
  const [status, setStatus] = useState<ConnectionStatus>('reconnecting');
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (typeof window === 'undefined' || typeof EventSource === 'undefined') return;

    const es = new EventSource(PRICE_STREAM_URL);
    sourceRef.current = es;

    es.onopen = () => setStatus('connected');

    es.onerror = () => {
      // readyState: CONNECTING(0) => browser is retrying; CLOSED(2) => gave up.
      setStatus(es.readyState === EventSource.CLOSED ? 'disconnected' : 'reconnecting');
    };

    const handleBatch = (raw: string) => {
      let batch: PriceUpdate[];
      try {
        batch = JSON.parse(raw);
      } catch {
        return;
      }
      if (!Array.isArray(batch) || batch.length === 0) return;

      setPrices((prev) => {
        const next = { ...prev };
        for (const u of batch) next[u.ticker] = u;
        return next;
      });
      setSparklines((prev) => {
        const next = { ...prev };
        for (const u of batch) {
          const series = next[u.ticker] ? [...next[u.ticker], u.price] : [u.price];
          if (series.length > MAX_SPARK_POINTS) series.shift();
          next[u.ticker] = series;
        }
        return next;
      });
    };

    es.addEventListener('price_update', (e) => handleBatch((e as MessageEvent).data));
    // Fall back to unnamed messages too, in case the server omits the event name.
    es.onmessage = (e) => handleBatch(e.data);

    return () => {
      es.close();
      sourceRef.current = null;
    };
  }, []);

  return { prices, sparklines, status };
}
