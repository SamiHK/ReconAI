'use client';
import { cn } from '@/lib/utils';
import { statusMeta, TONE_VAR } from '@/lib/petty-cash-report';

/** Status as glyph + word in its tone; the word is always present so colour never carries the meaning alone. */
export function StatusChip({ status }: { status: string | null }) {
  const { word, glyph, tone } = statusMeta(status);
  const c = TONE_VAR[tone];
  return (
    <span
      className="inline-flex h-5 shrink-0 items-center gap-1 whitespace-nowrap rounded-md px-2 text-[11px] font-semibold"
      style={{ color: c, background: `color-mix(in srgb, ${c} 12%, transparent)` }}
    >
      <b aria-hidden="true">{glyph}</b>
      {word}
    </span>
  );
}

/** A small mono button naming one source ("Receipt p82"); opens that source in the pane. */
export function CitationChip({ label, onClick, active = false, title }: { label: string; onClick: () => void; active?: boolean; title?: string }) {
  return (
    <button
      type="button"
      title={title}
      aria-pressed={active}
      onClick={e => {
        e.stopPropagation();
        onClick();
      }}
      className={cn(
        'inline-flex h-6 items-center whitespace-nowrap rounded-md border px-2 font-mono text-[11px] transition-colors',
        active
          ? 'border-primary bg-primary/10 text-primary'
          : 'border-border bg-card text-muted-foreground hover:border-primary/50 hover:text-foreground'
      )}
    >
      {label}
    </button>
  );
}

/** Pill filter with its count; counts come from the unfiltered list. */
export function FilterChip({ label, count, active, onClick }: { label: string; count: number; active: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        'inline-flex h-7 items-center gap-1.5 rounded-full px-3 text-xs font-medium transition-colors',
        active ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted hover:text-foreground'
      )}
    >
      {label}
      <span className="tabular-nums opacity-70">{count}</span>
    </button>
  );
}
