'use client';

import { useState } from 'react';
import { AppProvider } from '@/lib/store';
import Header from '@/components/Header';
import Watchlist from '@/components/Watchlist';
import MainChart from '@/components/MainChart';
import Heatmap from '@/components/Heatmap';
import PnLChart from '@/components/PnLChart';
import PositionsTable from '@/components/PositionsTable';
import TradeBar from '@/components/TradeBar';
import ChatPanel from '@/components/ChatPanel';

export default function Page() {
  const [chatOpen, setChatOpen] = useState(false);

  return (
    <AppProvider>
      <div className="flex h-dvh flex-col bg-bg-base text-slate-200">
        <Header onToggleChat={() => setChatOpen((v) => !v)} />

        <div className="flex min-h-0 flex-1">
          {/* Workspace */}
          <div className="flex min-h-0 flex-1 flex-col">
            <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto p-2 lg:flex-row lg:overflow-hidden">
              <div className="h-[300px] shrink-0 lg:h-auto lg:min-h-0 lg:w-[300px]">
                <Watchlist />
              </div>

              <div className="flex min-h-0 flex-1 flex-col gap-2">
                <div className="h-[300px] shrink-0 lg:h-auto lg:min-h-0 lg:flex-[1.5]">
                  <MainChart />
                </div>

                <div className="flex flex-col gap-2 sm:flex-row lg:min-h-0 lg:flex-1">
                  <div className="h-[240px] sm:flex-1 lg:h-auto lg:min-h-0">
                    <Heatmap />
                  </div>
                  <div className="h-[240px] sm:flex-1 lg:h-auto lg:min-h-0">
                    <PnLChart />
                  </div>
                </div>

                <div className="h-[280px] shrink-0 lg:h-auto lg:min-h-0 lg:flex-1">
                  <PositionsTable />
                </div>
              </div>
            </div>

            <TradeBar />
          </div>

          <ChatPanel open={chatOpen} onClose={() => setChatOpen(false)} />
        </div>
      </div>
    </AppProvider>
  );
}
