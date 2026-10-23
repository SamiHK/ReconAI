'use client';
import { useEffect, useState } from 'react';
import { LocateFixed, XIcon, ZoomIn, ZoomOut } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { imageUrl, money, type PaneSources, type PettyReport, type Source } from '@/lib/petty-cash-report';
import { LedgerLines } from './ledger-table';
import { PageStack, type PageBox } from './page-stack';

const ZOOM_MIN = 50;
const ZOOM_MAX = 300;
const ZOOM_STEP = 25;

const SOURCE_TABS: Array<{ key: Source; label: string }> = [
  { key: 'statement', label: 'Statement' },
  { key: 'receipt', label: 'Receipt' },
  { key: 'ledger', label: 'Ledger' },
];

/** Docked evidence pane: file header, zoom, jump-to-citation, and Statement / Receipt / Ledger tabs for one selection. */
export function CitationPane({ report, kbId, sources, initialSource, onClose }: {
  report: PettyReport;
  kbId: string;
  sources: PaneSources;
  initialSource: Source;
  onClose: () => void;
}) {
  const [source, setSource] = useState<Source>(initialSource);
  const [zoom, setZoom] = useState(100);
  const [jump, setJump] = useState(0);
  const [pageInView, setPageInView] = useState<number | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const available: Record<Source, boolean> = {
    statement: sources.statement.length > 0,
    receipt: sources.receipts.length > 0,
    ledger: sources.ledger !== null,
  };
  const isPages = source !== 'ledger';
  const images = isPages
    ? (source === 'statement' ? report.meta.page_images.statement : report.meta.page_images.receipts).map(p => imageUrl(kbId, p))
    : [];
  const boxes: PageBox[] =
    source === 'statement'
      ? sources.statement.flatMap((c, i) => (c.box ? [{ page: c.page, box: c.box, primary: i === 0, label: 'Statement row' }] : []))
      : source === 'receipt'
        ? sources.receipts.map((c, i) => ({ page: c.page, box: c.box, primary: i === sources.index, label: c.group_id }))
        : [];
  const activeIndex = source === 'receipt' ? sources.index : 0;
  const citedPage = boxes[activeIndex]?.page ?? boxes[0]?.page ?? 1;
  const fileName = report.meta.files[source === 'receipt' ? 'receipts' : source] ?? '';
  const ledger = sources.ledger;

  return (
    <aside aria-label="Evidence" className="flex h-full flex-col overflow-hidden rounded-xl border border-border bg-card shadow-sm">
      <div className="flex items-center gap-2 border-b border-border px-3 py-2">
        <p className="min-w-0 flex-1 truncate text-sm font-medium" title={sources.title}>{sources.title}</p>
        {isPages && (
          <div className="flex shrink-0 items-center gap-0.5">
            <Button variant="ghost" size="icon-sm" title="Zoom out" aria-label="Zoom out" disabled={zoom <= ZOOM_MIN} onClick={() => setZoom(z => Math.max(ZOOM_MIN, z - ZOOM_STEP))}>
              <ZoomOut className="size-4" />
            </Button>
            <span className="min-w-10 text-center text-xs tabular-nums text-muted-foreground">{zoom}%</span>
            <Button variant="ghost" size="icon-sm" title="Zoom in" aria-label="Zoom in" disabled={zoom >= ZOOM_MAX} onClick={() => setZoom(z => Math.min(ZOOM_MAX, z + ZOOM_STEP))}>
              <ZoomIn className="size-4" />
            </Button>
            <Button variant="ghost" size="icon-sm" title="Jump to citation" aria-label="Jump to citation" onClick={() => setJump(j => j + 1)}>
              <LocateFixed className="size-4" />
            </Button>
          </div>
        )}
        <Button variant="ghost" size="icon-sm" title="Close" aria-label="Close evidence pane" onClick={onClose}>
          <XIcon className="size-4" />
        </Button>
      </div>
      <div className="flex items-center gap-2 border-b border-border px-3 py-1.5">
        <div role="tablist" className="flex gap-1">
          {SOURCE_TABS.map(t => (
            <button
              key={t.key}
              type="button"
              role="tab"
              aria-selected={source === t.key}
              disabled={!available[t.key]}
              onClick={() => setSource(t.key)}
              className={cn(
                'h-7 rounded-full px-3 text-xs font-medium transition-colors disabled:opacity-40',
                source === t.key ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted hover:text-foreground disabled:hover:bg-transparent'
              )}
            >
              {t.label}
              {t.key === 'receipt' && sources.receipts.length > 1 && <span className="ml-1 tabular-nums opacity-70">{sources.receipts.length}</span>}
            </button>
          ))}
        </div>
        <p className="min-w-0 flex-1 truncate text-right text-[11px] text-muted-foreground" title={fileName}>
          {fileName}
          {isPages && images.length > 0 && ` · page ${pageInView ?? citedPage} of ${images.length}`}
        </p>
      </div>
      <div className="min-h-0 flex-1">
        {isPages ? (
          <PageStack images={images} boxes={boxes} activeIndex={activeIndex} jumpSignal={jump} zoom={zoom} onPageInView={setPageInView} />
        ) : ledger ? (
          <div className="h-full space-y-2 overflow-auto p-3">
            <p className="text-xs text-muted-foreground">
              {ledger.cell} · {ledger.code} · {money(ledger.amount)} ·{' '}
              {ledger.relation === 'rolled-up'
                ? 'this row is rolled up into the line below'
                : ledger.relation === 'tied'
                  ? 'this row is tied to the line below'
                  : ledger.relation}
            </p>
            <LedgerLines lines={report.ledger.filter(l => l.month === report.meta.month)} highlightCode={ledger.code} />
          </div>
        ) : null}
      </div>
    </aside>
  );
}
