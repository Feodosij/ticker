import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { usePriceStream } from './usePriceStream';

// Minimal EventSource stand-in so we can drive open/error/message in tests.
class MockEventSource {
  static instances: MockEventSource[] = [];
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSED = 2;

  url: string;
  readyState = MockEventSource.CONNECTING;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  listeners: Record<string, (e: MessageEvent) => void> = {};

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }
  addEventListener(type: string, fn: (e: MessageEvent) => void) {
    this.listeners[type] = fn;
  }
  emit(type: string, data: string) {
    this.listeners[type]?.({ data } as MessageEvent);
  }
  close() {
    this.readyState = MockEventSource.CLOSED;
  }
}

beforeEach(() => {
  MockEventSource.instances = [];
  vi.stubGlobal('EventSource', MockEventSource as unknown as typeof EventSource);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('usePriceStream', () => {
  it('starts in a reconnecting state and flips to connected on open', async () => {
    const { result } = renderHook(() => usePriceStream());
    expect(result.current.status).toBe('reconnecting');

    const es = MockEventSource.instances[0];
    act(() => {
      es.readyState = MockEventSource.OPEN;
      es.onopen?.();
    });
    await waitFor(() => expect(result.current.status).toBe('connected'));
  });

  it('parses price_update batches into prices and sparklines', async () => {
    const { result } = renderHook(() => usePriceStream());
    const es = MockEventSource.instances[0];

    act(() => {
      es.emit(
        'price_update',
        JSON.stringify([
          { ticker: 'AAPL', price: 190, previous_price: 189, change_direction: 'up', change_pct: 0.5, timestamp: 't1' },
        ]),
      );
    });
    act(() => {
      es.emit(
        'price_update',
        JSON.stringify([
          { ticker: 'AAPL', price: 191, previous_price: 190, change_direction: 'up', change_pct: 1.0, timestamp: 't2' },
        ]),
      );
    });

    await waitFor(() => {
      expect(result.current.prices.AAPL.price).toBe(191);
      expect(result.current.sparklines.AAPL).toEqual([190, 191]);
    });
  });

  it('marks disconnected when the source closes', async () => {
    const { result } = renderHook(() => usePriceStream());
    const es = MockEventSource.instances[0];
    act(() => {
      es.readyState = MockEventSource.CLOSED;
      es.onerror?.();
    });
    await waitFor(() => expect(result.current.status).toBe('disconnected'));
  });
});
