'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { api } from './api';
import { usePriceStream } from './usePriceStream';
import type {
  ApiPortfolio,
  ChatMessage,
  ConnectionStatus,
  PortfolioSnapshot,
  PriceUpdate,
  TradeRequest,
  WatchlistItem,
} from './types';

interface AppState {
  // live market data
  prices: Record<string, PriceUpdate>;
  sparklines: Record<string, number[]>;
  status: ConnectionStatus;
  // resources
  portfolio: ApiPortfolio | null;
  history: PortfolioSnapshot[];
  watchlist: WatchlistItem[];
  selectedTicker: string | null;
  // chat
  chatMessages: ChatMessage[];
  chatLoading: boolean;
  // errors surfaced to the UI (trade bar / watchlist)
  actionError: string | null;
  // actions
  selectTicker: (t: string) => void;
  executeTrade: (req: TradeRequest) => Promise<boolean>;
  addTicker: (t: string) => Promise<boolean>;
  removeTicker: (t: string) => Promise<void>;
  sendChat: (message: string) => Promise<void>;
  clearActionError: () => void;
}

const AppContext = createContext<AppState | null>(null);

let idCounter = 0;
const nextId = () => `${Date.now()}-${idCounter++}`;

export function AppProvider({ children }: { children: React.ReactNode }) {
  const { prices, sparklines, status } = usePriceStream();

  const [portfolio, setPortfolio] = useState<ApiPortfolio | null>(null);
  const [history, setHistory] = useState<PortfolioSnapshot[]>([]);
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const selectedInitialized = useRef(false);

  const refreshPortfolio = useCallback(async () => {
    try {
      const p = await api.getPortfolio();
      setPortfolio(p);
    } catch {
      /* backend may not be up yet; leave prior state */
    }
  }, []);

  const refreshHistory = useCallback(async () => {
    try {
      setHistory(await api.getPortfolioHistory());
    } catch {
      /* ignore */
    }
  }, []);

  const refreshWatchlist = useCallback(async () => {
    try {
      setWatchlist(await api.getWatchlist());
    } catch {
      /* ignore */
    }
  }, []);

  // Initial load + periodic portfolio/history refresh (30s snapshot cadence).
  useEffect(() => {
    refreshPortfolio();
    refreshHistory();
    refreshWatchlist();
    const id = setInterval(() => {
      refreshPortfolio();
      refreshHistory();
    }, 30_000);
    return () => clearInterval(id);
  }, [refreshPortfolio, refreshHistory, refreshWatchlist]);

  // Default the main chart to the first watchlist ticker once loaded.
  useEffect(() => {
    if (!selectedInitialized.current && watchlist.length > 0) {
      setSelectedTicker(watchlist[0].ticker);
      selectedInitialized.current = true;
    }
  }, [watchlist]);

  const selectTicker = useCallback((t: string) => setSelectedTicker(t), []);
  const clearActionError = useCallback(() => setActionError(null), []);

  const executeTrade = useCallback(
    async (req: TradeRequest): Promise<boolean> => {
      setActionError(null);
      try {
        // Trade returns a partial result; resync the full portfolio + history.
        await api.trade(req);
        await refreshPortfolio();
        refreshHistory();
        return true;
      } catch (e) {
        setActionError(e instanceof Error ? e.message : 'Trade failed');
        return false;
      }
    },
    [refreshPortfolio, refreshHistory],
  );

  const addTicker = useCallback(
    async (t: string): Promise<boolean> => {
      setActionError(null);
      const ticker = t.trim().toUpperCase();
      if (!ticker) return false;
      try {
        // Add returns the single new entry; resync the full list for ordering.
        await api.addWatchlist(ticker);
        await refreshWatchlist();
        return true;
      } catch (e) {
        setActionError(e instanceof Error ? e.message : 'Could not add ticker');
        return false;
      }
    },
    [refreshWatchlist],
  );

  const removeTicker = useCallback(
    async (t: string) => {
      setActionError(null);
      try {
        await api.removeWatchlist(t);
        await refreshWatchlist();
      } catch (e) {
        setActionError(e instanceof Error ? e.message : 'Could not remove ticker');
      }
      if (selectedTicker === t) setSelectedTicker(null);
    },
    [refreshWatchlist, selectedTicker],
  );

  const sendChat = useCallback(
    async (message: string) => {
      const text = message.trim();
      if (!text) return;
      const userMsg: ChatMessage = { id: nextId(), role: 'user', content: text };
      const pendingId = nextId();
      setChatMessages((prev) => [
        ...prev,
        userMsg,
        { id: pendingId, role: 'assistant', content: '', pending: true },
      ]);
      setChatLoading(true);
      try {
        const res = await api.chat(text);
        setChatMessages((prev) =>
          prev.map((m) =>
            m.id === pendingId
              ? {
                  ...m,
                  content: res.message,
                  trades: res.trades,
                  watchlist_changes: res.watchlist_changes,
                  pending: false,
                }
              : m,
          ),
        );
        // Chat can mutate portfolio + watchlist; resync from source of truth.
        if (res.trades?.length) refreshPortfolio();
        if (res.watchlist_changes?.length) refreshWatchlist();
      } catch (e) {
        setChatMessages((prev) =>
          prev.map((m) =>
            m.id === pendingId
              ? {
                  ...m,
                  content:
                    e instanceof Error
                      ? `Couldn't reach the assistant: ${e.message}`
                      : "Couldn't reach the assistant.",
                  pending: false,
                }
              : m,
          ),
        );
      } finally {
        setChatLoading(false);
      }
    },
    [refreshPortfolio, refreshWatchlist],
  );

  const value = useMemo<AppState>(
    () => ({
      prices,
      sparklines,
      status,
      portfolio,
      history,
      watchlist,
      selectedTicker,
      chatMessages,
      chatLoading,
      actionError,
      selectTicker,
      executeTrade,
      addTicker,
      removeTicker,
      sendChat,
      clearActionError,
    }),
    [
      prices,
      sparklines,
      status,
      portfolio,
      history,
      watchlist,
      selectedTicker,
      chatMessages,
      chatLoading,
      actionError,
      selectTicker,
      executeTrade,
      addTicker,
      removeTicker,
      sendChat,
      clearActionError,
    ],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppState {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used within AppProvider');
  return ctx;
}
