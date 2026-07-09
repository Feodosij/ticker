import type { ConnectionStatus } from '@/lib/types';

const CONFIG: Record<ConnectionStatus, { color: string; label: string; pulse: boolean }> = {
  connected: { color: 'bg-up', label: 'Live', pulse: false },
  reconnecting: { color: 'bg-accent', label: 'Reconnecting', pulse: true },
  disconnected: { color: 'bg-down', label: 'Disconnected', pulse: false },
};

export default function StatusDot({ status }: { status: ConnectionStatus }) {
  const { color, label, pulse } = CONFIG[status];
  return (
    <div className="flex items-center gap-2" role="status" aria-label={`Connection: ${label}`}>
      <span
        data-status={status}
        className={`h-2.5 w-2.5 rounded-full ${color} ${pulse ? 'animate-pulse-dot' : ''}`}
      />
      <span className="text-xs uppercase tracking-wide text-muted">{label}</span>
    </div>
  );
}
