// Types for data/<client>/report.json (written by scripts/abujhd/c_report.py) and the pure helpers the
// petty-cash report components share. Nothing here touches the DOM.

export type Box = [number, number, number, number]; // x0, y0, x1, y1 in the matcher's 0-1000 page space

export interface StatementCitation { page: number; box: Box; crop: string }
export interface ReceiptCitation { page: number; group_id: string; box: Box; crop: string }
export interface LedgerCitation { sheet: string; row: number; cell: string; code: string; date: string; amount: number; relation: string }

export interface StatementRow {
  ref: string;
  date: string;
  time: string | null;
  amount: number;
  merchant: string;
  kind: 'purchase' | 'atm' | 'load';
  orange: boolean;
  status: string;
  reason: string;
  receipt_ids: string[];
  citations: { statement: StatementCitation; receipts: ReceiptCitation[]; ledger: LedgerCitation | null };
}

export interface ReceiptGroup {
  id: string;
  page: number;
  pages: number[];
  box: Box;
  crop: string | null;
  status: string;
  reason: string | null;
  merchant: string | null;
  date: string | null;
  total: number | null;
  amounts: number[];
  confidence: number | null;
  notes: string | null;
  refs: string[];
  review: Array<[string, number]>;
  citations: ReceiptCitation[];
}

export interface LedgerLine {
  code: string;
  date: string;
  text: string;
  debit: number | null;
  credit: number | null;
  balance: number | null;
  month: string;
  row: number;
  cell: string;
  status: string | null;
}

interface Pair { statement: number; ledger: number; diff: number }

export interface PettyReport {
  meta: {
    client: string;
    month: string;
    month_label: string;
    built_at: string;
    sheet: string;
    files: Record<string, string>;
    page_images: { receipts: string[]; statement: string[] };
  };
  kpis: {
    card_spend: number; purchase_count: number; atm_count: number; purchases_amount: number; evidenced_amount: number;
    rollup: number; open_gap: number; missing_count: number; missing_amount: number;
  };
  counts: { rows: Record<string, number>; receipts: Record<string, number> };
  rows: StatementRow[];
  receipts: ReceiptGroup[];
  ledger: LedgerLine[];
  tieout: { loads_vs_topups: Pair; atm_vs_withdrawals: Pair; purchases_vs_rollup: Pair & { purchases_only: number; rollup_codes: string[] } };
}

// ---------- status vocabulary: a word, a glyph and a tone; colour never carries the meaning alone ----------
export type Tone = 'ok' | 'bad' | 'review' | 'warn' | 'muted';
export const TONE_VAR: Record<Tone, string> = {
  ok: 'var(--status-ok)',
  bad: 'var(--status-bad)',
  review: 'var(--status-review)',
  warn: 'var(--status-warn)',
  muted: 'var(--muted-foreground)',
};
const STATUS: Record<string, { word: string; glyph: string; tone: Tone }> = {
  MATCHED: { word: 'Matched', glyph: '✓', tone: 'ok' },
  LINKED: { word: 'Linked', glyph: '✓', tone: 'ok' },
  TIED: { word: 'Tied to ledger', glyph: '✓', tone: 'ok' },
  MISSING_RECEIPT: { word: 'Missing receipt', glyph: '✕', tone: 'bad' },
  ORPHAN: { word: 'No card row', glyph: '✕', tone: 'bad' },
  REVIEW: { word: 'Needs a decision', glyph: '?', tone: 'review' },
  UNEXPLAINED: { word: 'Not in ledger', glyph: '!', tone: 'warn' },
  AMOUNT_MISMATCH: { word: 'Amounts differ', glyph: '!', tone: 'warn' },
  OTHER_MONTH: { word: 'Another month', glyph: '!', tone: 'warn' },
  ROLLUP: { word: 'Roll-up of card spend', glyph: '·', tone: 'muted' },
  NO_CARD_TXN: { word: 'No card transaction', glyph: '!', tone: 'warn' },
};
export function statusMeta(status: string | null): { word: string; glyph: string; tone: Tone } {
  return (status && STATUS[status]) || { word: status ?? '—', glyph: '·', tone: 'muted' };
}

// ---------- filters, counts, sort ----------
export const ROW_FILTERS = [
  { key: 'ALL', label: 'All' },
  { key: 'MATCHED', label: 'Matched' },
  { key: 'REVIEW', label: 'Needs a decision' },
  { key: 'MISSING_RECEIPT', label: 'Missing receipt' },
  { key: 'AMOUNT_MISMATCH', label: 'Amounts differ' },
  { key: 'UNEXPLAINED', label: 'Not in ledger' },
  { key: 'TIED', label: 'Tied to ledger' },
];
export const RECEIPT_FILTERS = [
  { key: 'ALL', label: 'All' },
  { key: 'LINKED', label: 'Linked' },
  { key: 'REVIEW', label: 'Needs a decision' },
  { key: 'ORPHAN', label: 'No card row' },
  { key: 'OTHER_MONTH', label: 'Another month' },
];

/** Counts per status plus ALL; computed over the unfiltered list so chip counts never shrink. */
export function countByStatus(items: Array<{ status: string }>): Record<string, number> {
  const out: Record<string, number> = { ALL: items.length };
  for (const it of items) out[it.status] = (out[it.status] ?? 0) + 1;
  return out;
}

export function filterRows(rows: StatementRow[], status: string, query: string): StatementRow[] {
  const q = query.trim().toLowerCase();
  return rows.filter(
    r =>
      (status === 'ALL' || r.status === status) &&
      (!q || r.merchant.toLowerCase().includes(q) || r.ref.toLowerCase().includes(q) || r.amount.toFixed(2).includes(q))
  );
}

export function filterReceipts(groups: ReceiptGroup[], status: string): ReceiptGroup[] {
  return status === 'ALL' ? groups : groups.filter(g => g.status === status);
}

export type SortKey = 'date' | 'amount';
export function sortRows(rows: StatementRow[], key: SortKey, dir: 'asc' | 'desc'): StatementRow[] {
  const sign = dir === 'asc' ? 1 : -1;
  return [...rows].sort((a, b) => {
    const d = key === 'amount' ? a.amount - b.amount : (a.date + (a.time ?? '')).localeCompare(b.date + (b.time ?? ''));
    return d * sign;
  });
}

// ---------- formatting and geometry ----------
export function money(n: number | null | undefined): string {
  return typeof n === 'number' ? n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '';
}
export function pct(num: number, den: number): string {
  return den ? `${Math.round((num / den) * 100)}%` : '0%';
}
/** A 0-1000 box as percentage offsets inside its page element. */
export function boxStyle([x0, y0, x1, y1]: Box): { left: string; top: string; width: string; height: string } {
  return { left: `${x0 / 10}%`, top: `${y0 / 10}%`, width: `${(x1 - x0) / 10}%`, height: `${(y1 - y0) / 10}%` };
}
export function imageUrl(kbId: string, path: string): string {
  return `/api/petty-cash/${kbId}/${path}`;
}

// ---------- what the citation pane shows for a selection ----------
export type Source = 'statement' | 'receipt' | 'ledger';
export type Selection =
  | { kind: 'row'; ref: string; source: Source; index?: number } // index: which receipt citation is primary
  | { kind: 'receipt'; id: string; source: Source };

export interface PaneSources {
  title: string;
  statement: StatementCitation[];
  receipts: ReceiptCitation[];
  ledger: LedgerCitation | null;
  index: number;
}

export function rowByRef(report: PettyReport, ref: string): StatementRow | undefined {
  return report.rows.find(r => r.ref === ref);
}

export function paneSources(report: PettyReport, sel: Selection): PaneSources | null {
  if (sel.kind === 'row') {
    const row = rowByRef(report, sel.ref);
    if (!row) return null;
    return {
      title: `${row.date} · ${money(row.amount)} · ${row.merchant}`,
      statement: [row.citations.statement],
      receipts: row.citations.receipts,
      ledger: row.citations.ledger,
      index: sel.index ?? 0,
    };
  }
  const g = report.receipts.find(x => x.id === sel.id);
  if (!g) return null;
  const refs = new Set([...g.refs, ...g.review.map(([ref]) => ref)]);
  const rows = report.rows.filter(r => refs.has(r.ref));
  return {
    title: `${g.merchant ?? g.id} · p${g.page}`,
    statement: rows.map(r => r.citations.statement),
    receipts: g.citations,
    ledger: rows[0]?.citations.ledger ?? null,
    index: 0,
  };
}
