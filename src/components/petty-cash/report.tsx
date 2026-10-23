'use client';
import { useCallback, useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { money, paneSources, pct, type PettyReport, type Selection } from '@/lib/petty-cash-report';
import { CitationPane } from './citation-pane';
import { LedgerTable } from './ledger-table';
import { ReceiptsTable } from './receipts-table';
import { TransactionsTable } from './transactions-table';

type Tab = 'transactions' | 'receipts' | 'ledger';
const TABS: Array<{ key: Tab; label: string; count: (r: PettyReport) => number }> = [
  { key: 'transactions', label: 'Transactions', count: r => r.rows.length },
  { key: 'receipts', label: 'Receipts', count: r => r.receipts.length },
  { key: 'ledger', label: 'Ledger', count: r => r.ledger.length },
];

function Tile({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <Card size="sm" className="gap-1 px-4">
      <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="text-[28px] font-semibold leading-tight tabular-nums">{value}</div>
      <div className="text-xs text-muted-foreground">{sub}</div>
    </Card>
  );
}

/** The petty-cash report for one workspace: KPI tiles, three tabbed tables and the docked citation pane. */
export function PettyCashReport({ kbId, version }: { kbId: string; version: number }) {
  const [state, setState] = useState<{ report: PettyReport | null; error: string | null }>({ report: null, error: null });
  const [attempt, setAttempt] = useState(0);
  const [tab, setTab] = useState<Tab>('transactions');
  const [selection, setSelection] = useState<Selection | null>(null);

  // `version` is the Run counter: a new run re-fetches; the previous report stays on screen until the new one lands.
  useEffect(() => {
    let cancelled = false;
    fetch(`/api/petty-cash/${kbId}/report.json?v=${version}`, { cache: 'no-store' })
      .then(async r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return (await r.json()) as PettyReport;
      })
      .then(report => {
        if (!cancelled) setState({ report, error: null });
      })
      .catch((e: unknown) => {
        if (!cancelled) setState({ report: null, error: e instanceof Error ? e.message : 'Failed to load' });
      });
    return () => {
      cancelled = true;
    };
  }, [kbId, version, attempt]);

  const closePane = useCallback(() => setSelection(null), []);
  const onSelect = useCallback((s: Selection) => setSelection(s), []);

  if (state.error) {
    return (
      <Card className="px-6 py-6 text-sm">
        <p className="mb-3">Couldn&apos;t load the petty-cash report ({state.error}).</p>
        <Button
          size="sm"
          onClick={() => {
            setState({ report: null, error: null });
            setAttempt(a => a + 1);
          }}
        >
          Retry
        </Button>
      </Card>
    );
  }
  const report = state.report;
  if (!report) {
    return (
      <div className="flex justify-center py-16">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const sources = selection ? paneSources(report, selection) : null;
  const selectionKey = selection ? JSON.stringify(selection) : '';
  const k = report.kpis;
  const built = new Date(report.meta.built_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });

  return (
    <div className={cn('gap-4', sources && 'lg:grid lg:grid-cols-[minmax(0,1fr)_minmax(420px,45%)]')}>
      <div className="min-w-0 space-y-4">
        <header>
          <h3 className="text-h3">{report.meta.client} · {report.meta.month_label}</h3>
          <p className="text-xs text-muted-foreground">Statement · receipts · ledger · built {built}</p>
        </header>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Tile label="Card spend" value={money(k.card_spend)} sub={`SAR · ${k.purchase_count} purchases + ${k.atm_count} ATM withdrawals`} />
          <Tile label="Evidenced" value={pct(k.evidenced_amount, k.purchases_amount)} sub={`${money(k.evidenced_amount)} of ${money(k.purchases_amount)} SAR has a matched receipt`} />
          <Tile label="Open gap" value={money(k.open_gap)} sub={`ledger roll-up ${money(k.rollup)} minus card spend`} />
          <Tile label="Receipts to find" value={String(k.missing_count)} sub={`${money(k.missing_amount)} SAR without a receipt`} />
        </div>
        <div role="tablist" className="flex flex-wrap gap-1">
          {TABS.map(t => (
            <button
              key={t.key}
              type="button"
              role="tab"
              aria-selected={tab === t.key}
              onClick={() => setTab(t.key)}
              className={cn(
                'h-8 rounded-full px-3 text-sm font-medium transition-colors',
                tab === t.key ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              )}
            >
              {t.label} <span className="tabular-nums opacity-70">{t.count(report)}</span>
            </button>
          ))}
        </div>
        {tab === 'transactions' && <TransactionsTable rows={report.rows} selection={selection} onSelect={onSelect} />}
        {tab === 'receipts' && <ReceiptsTable report={report} kbId={kbId} selection={selection} onSelect={onSelect} />}
        {tab === 'ledger' && <LedgerTable report={report} />}
      </div>
      {sources && selection && (
        <div className="fixed inset-0 z-50 bg-background/95 p-3 lg:sticky lg:inset-auto lg:top-4 lg:z-auto lg:h-[calc(100vh-7rem)] lg:bg-transparent lg:p-0">
          <CitationPane key={selectionKey} report={report} kbId={kbId} sources={sources} initialSource={selection.source} onClose={closePane} />
        </div>
      )}
    </div>
  );
}
