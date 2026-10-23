'use client';
import { useMemo, useState } from 'react';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, TABLE_HEAD_BAND } from '@/components/ui/table';
import { cn } from '@/lib/utils';
import {
  countByStatus, filterRows, money, ROW_FILTERS, sortRows,
  type Selection, type SortKey, type StatementRow,
} from '@/lib/petty-cash-report';
import { CitationChip, FilterChip, StatusChip } from './chips';

/** `compact` drops the Note column so the table fits beside the docked pane. */
export function TransactionsTable({ rows, selection, onSelect, compact = false }: { rows: StatementRow[]; selection: Selection | null; onSelect: (s: Selection) => void; compact?: boolean }) {
  const [status, setStatus] = useState('ALL');
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState<{ key: SortKey; dir: 'asc' | 'desc' }>({ key: 'date', dir: 'asc' });
  const counts = useMemo(() => countByStatus(rows), [rows]);
  const visible = useMemo(() => sortRows(filterRows(rows, status, query), sort.key, sort.dir), [rows, status, query, sort]);

  const toggleSort = (key: SortKey) => setSort(s => ({ key, dir: s.key === key && s.dir === 'asc' ? 'desc' : 'asc' }));
  const sortMark = (key: SortKey) => (sort.key === key ? (sort.dir === 'asc' ? ' ▲' : ' ▼') : '');
  const ariaSort = (key: SortKey) => (sort.key === key ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none');
  const selectedRef = selection?.kind === 'row' ? selection.ref : null;
  const chipActive = (ref: string, source: string, index = 0) =>
    selection?.kind === 'row' && selection.ref === ref && selection.source === source && (selection.index ?? 0) === index;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-1">
        {ROW_FILTERS.map(f => (
          <FilterChip key={f.key} label={f.label} count={counts[f.key] ?? 0} active={status === f.key} onClick={() => setStatus(f.key)} />
        ))}
        <Input
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Merchant, ref or amount"
          aria-label="Search transactions"
          className="ml-auto h-7 w-56 text-xs"
        />
      </div>
      <div className="overflow-hidden rounded-xl border border-border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className={TABLE_HEAD_BAND}>Status</TableHead>
              <TableHead className={TABLE_HEAD_BAND} aria-sort={ariaSort('date')}>
                <button type="button" onClick={() => toggleSort('date')}>Date<span aria-hidden="true">{sortMark('date')}</span></button>
              </TableHead>
              <TableHead className={cn(TABLE_HEAD_BAND, 'text-right')} aria-sort={ariaSort('amount')}>
                <button type="button" onClick={() => toggleSort('amount')}>Amount<span aria-hidden="true">{sortMark('amount')}</span></button>
              </TableHead>
              <TableHead className={TABLE_HEAD_BAND}>Merchant</TableHead>
              <TableHead className={TABLE_HEAD_BAND}>Evidence</TableHead>
              {!compact && <TableHead className={TABLE_HEAD_BAND}>Note</TableHead>}
            </TableRow>
          </TableHeader>
          <TableBody>
            {visible.length === 0 && (
              <TableRow>
                <TableCell colSpan={compact ? 5 : 6} className="py-6 text-center text-muted-foreground">No rows match</TableCell>
              </TableRow>
            )}
            {visible.map(r => (
              <TableRow
                key={r.ref}
                aria-selected={selectedRef === r.ref}
                onClick={() => onSelect({ kind: 'row', ref: r.ref, source: r.citations.receipts.length ? 'receipt' : 'statement' })}
                className={cn('cursor-pointer', selectedRef === r.ref ? 'bg-primary/5 hover:bg-primary/5' : 'hover:bg-muted/40')}
              >
                <TableCell><StatusChip status={r.status} /></TableCell>
                <TableCell className="whitespace-nowrap font-mono text-xs">
                  <div className="flex items-center gap-1.5">
                    {r.date}
                    {r.orange && <span className="size-2 rounded-full bg-amber-500" title="Highlighted on the statement" />}
                  </div>
                  <div className="text-muted-foreground">{(r.time ?? '').slice(0, 5)}</div>
                </TableCell>
                <TableCell className="text-right font-mono text-xs tabular-nums">{money(r.amount)}</TableCell>
                <TableCell className={cn('max-w-[260px]', compact && 'max-w-[160px]')}>
                  <div className="truncate" title={r.merchant}>{r.merchant}</div>
                  <div className="text-xs text-muted-foreground">{r.kind}</div>
                </TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-1">
                    <CitationChip label="Stmt" title="Statement row" active={chipActive(r.ref, 'statement')} onClick={() => onSelect({ kind: 'row', ref: r.ref, source: 'statement' })} />
                    {r.citations.receipts.map((c, i) => (
                      <CitationChip key={c.group_id} label={`Receipt p${c.page}`} title={c.group_id} active={chipActive(r.ref, 'receipt', i)} onClick={() => onSelect({ kind: 'row', ref: r.ref, source: 'receipt', index: i })} />
                    ))}
                    {r.citations.ledger && (
                      <CitationChip label={`Ledger ${r.citations.ledger.cell}`} title={r.citations.ledger.code} active={chipActive(r.ref, 'ledger')} onClick={() => onSelect({ kind: 'row', ref: r.ref, source: 'ledger' })} />
                    )}
                  </div>
                </TableCell>
                {!compact && <TableCell className="max-w-[280px] text-xs text-muted-foreground">{r.reason}</TableCell>}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
