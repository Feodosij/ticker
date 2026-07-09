interface Props {
  title: string;
  right?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  bodyClassName?: string;
}

export default function Panel({ title, right, children, className = '', bodyClassName = '' }: Props) {
  return (
    <section
      className={`flex h-full w-full min-h-0 flex-col overflow-hidden rounded-lg border border-border bg-bg-panel ${className}`}
    >
      <header className="flex items-center justify-between border-b border-border px-3 py-2">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted">
          {title}
        </h2>
        {right}
      </header>
      <div className={`min-h-0 flex-1 overflow-auto ${bodyClassName}`}>{children}</div>
    </section>
  );
}
