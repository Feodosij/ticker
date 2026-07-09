'use client';

import { useEffect, useRef, useState } from 'react';
import { useApp } from '@/lib/store';
import { formatQty } from '@/lib/format';
import type { ChatMessage } from '@/lib/types';

export default function ChatPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { chatMessages, chatLoading, sendChat } = useApp();
  const [draft, setDraft] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [chatMessages]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!draft.trim() || chatLoading) return;
    sendChat(draft);
    setDraft('');
  };

  return (
    <>
      {/* Mobile scrim */}
      <div
        onClick={onClose}
        className={`fixed inset-0 z-20 bg-black/50 lg:hidden ${open ? 'block' : 'hidden'}`}
      />
      <aside
        className={`fixed right-0 top-0 z-30 flex h-full w-[340px] max-w-[88vw] flex-col border-l border-border bg-bg-panel transition-transform lg:static lg:z-auto lg:h-auto lg:w-[340px] lg:max-w-none lg:translate-x-0 ${
          open ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        <header className="flex items-center justify-between border-b border-border px-3 py-2.5">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-accent" />
            <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-200">
              FinAlly Copilot
            </h2>
          </div>
          <button
            onClick={onClose}
            aria-label="Close chat"
            className="text-faint transition-colors hover:text-slate-200 lg:hidden"
          >
            ×
          </button>
        </header>

        <div ref={scrollRef} className="min-h-0 flex-1 space-y-3 overflow-y-auto p-3">
          {chatMessages.length === 0 && (
            <div className="mt-6 space-y-2 text-center">
              <p className="text-sm text-muted">Ask FinAlly to analyze or trade.</p>
              <p className="text-xs text-faint">
                &ldquo;How is my portfolio concentrated?&rdquo;
                <br />
                &ldquo;Buy 5 shares of NVDA&rdquo;
              </p>
            </div>
          )}
          {chatMessages.map((m) => (
            <MessageBubble key={m.id} message={m} />
          ))}
        </div>

        <form onSubmit={submit} className="border-t border-border p-2.5">
          <div className="flex items-end gap-2">
            <textarea
              aria-label="Message FinAlly"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) submit(e);
              }}
              rows={1}
              placeholder="Message FinAlly…"
              className="max-h-28 min-h-[38px] flex-1 resize-none rounded border border-border bg-bg-base px-2.5 py-2 text-sm text-slate-100 placeholder:text-faint focus:border-primary focus:outline-none"
            />
            <button
              type="submit"
              disabled={!draft.trim() || chatLoading}
              className="rounded bg-secondary px-3 py-2 text-sm font-semibold text-white transition-colors hover:bg-secondary/85 disabled:opacity-40"
            >
              Send
            </button>
          </div>
        </form>
      </aside>
    </>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user';
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
          isUser
            ? 'bg-primary/15 text-slate-100'
            : 'border border-border bg-bg-raised text-slate-200'
        }`}
      >
        {message.pending ? (
          <TypingDots />
        ) : (
          <p className="whitespace-pre-wrap leading-snug">{message.content}</p>
        )}

        {message.trades && message.trades.length > 0 && (
          <div className="mt-2 space-y-1">
            {message.trades.map((t, i) => (
              <ActionChip
                key={i}
                ok={!t.error}
                text={
                  t.error
                    ? `${t.side.toUpperCase()} ${formatQty(t.quantity)} ${t.ticker} failed: ${t.error}`
                    : `${t.side === 'buy' ? 'Bought' : 'Sold'} ${formatQty(t.quantity)} ${t.ticker} @ ${t.price.toFixed(2)}`
                }
              />
            ))}
          </div>
        )}

        {message.watchlist_changes && message.watchlist_changes.length > 0 && (
          <div className="mt-2 space-y-1">
            {message.watchlist_changes.map((w, i) => (
              <ActionChip
                key={i}
                ok={!w.error}
                text={
                  w.error
                    ? `${w.action} ${w.ticker} failed: ${w.error}`
                    : `${w.action === 'add' ? 'Added' : 'Removed'} ${w.ticker} ${
                        w.action === 'add' ? 'to' : 'from'
                      } watchlist`
                }
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ActionChip({ ok, text }: { ok: boolean; text: string }) {
  return (
    <div
      className={`flex items-center gap-1.5 rounded border px-2 py-1 font-mono text-[11px] ${
        ok ? 'border-up/40 bg-up/10 text-up' : 'border-down/40 bg-down/10 text-down'
      }`}
    >
      <span>{ok ? '✓' : '✕'}</span>
      <span>{text}</span>
    </div>
  );
}

function TypingDots() {
  return (
    <span className="flex items-center gap-1 py-1" aria-label="Assistant is typing">
      <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-muted" />
      <span
        className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-muted"
        style={{ animationDelay: '0.2s' }}
      />
      <span
        className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-muted"
        style={{ animationDelay: '0.4s' }}
      />
    </span>
  );
}
