import { describe, test, expect } from 'bun:test';
import {
  boxStyle, countByStatus, filterReceipts, filterRows, imageUrl, money, paneSources, pct, rowByRef, sortRows, statusMeta,
  type Box, type PettyReport, type ReceiptGroup, type StatementRow,
} from '../petty-cash-report';

const BOX: Box = [100, 100, 500, 900];
function row(ref: string, date: string, time: string | null, amount: number, merchant: string, status: string,
  receipts: Array<{ page: number; group_id: string }> = [], ledger = true): StatementRow {
  return {
    ref, date, time, amount, merchant, kind: 'purchase', orange: false, status, reason: 'why',
    receipt_ids: receipts.map(r => r.group_id),
    citations: {
      statement: { page: 1, box: [0, 10, 1000, 15], crop: `crops/stmt-${ref}.png` },
      receipts: receipts.map(r => ({ ...r, box: BOX, crop: `crops/${r.group_id}.png` })),
      ledger: ledger ? { sheet: 'GL', row: 9, cell: 'B9', code: 'ROLL', date: '2026-09-30', amount: 300, relation: 'rolled-up' } : null,
    },
  };
}
function group(id: string, page: number, status: string, refs: string[] = [], review: Array<[string, number]> = []): ReceiptGroup {
  return {
    id, page, pages: [page], box: [100, 100, 500, 900], crop: `crops/${id}.png`, status, reason: 'r', merchant: `Shop ${id}`,
    date: '2026-09-04', total: 20, amounts: [20], confidence: 0.9, notes: null, refs, review,
    citations: [{ page, group_id: id, box: [100, 100, 500, 900], crop: `crops/${id}.png` }],
  };
}
const REPORT: PettyReport = {
  meta: {
    client: 'ABUJHD', month: '2026-09', month_label: 'September 2026', built_at: '2026-10-23T22:00:00', sheet: 'GL',
    files: { receipts: 'r.pdf', statement: 's.pdf', ledger: 'l.xlsx' },
    page_images: { receipts: ['pages/page-01.png', 'pages/page-02.png'], statement: ['pages/statement-200.png'] },
  },
  kpis: { card_spend: 350, purchase_count: 2, atm_count: 1, purchases_amount: 150, evidenced_amount: 100, rollup: 300, open_gap: -50, missing_count: 1, missing_amount: 50 },
  counts: { rows: {}, receipts: {} },
  rows: [
    row('r1', '2026-09-05', '10:00:00', 100, 'GREEN STAR FUEL', 'MATCHED', [{ page: 1, group_id: 'p1-g1' }, { page: 2, group_id: 'p2-g1' }]),
    row('r2', '2026-09-05', '08:00:00', 50, 'AL OTHAIM', 'MISSING_RECEIPT'),
    row('r3', '2026-09-01', null, 75.5, 'MAZA REST', 'REVIEW', [], false),
  ],
  receipts: [group('p1-g1', 1, 'LINKED', ['r1']), group('p2-g1', 2, 'LINKED', ['r1']), group('p3-g1', 3, 'REVIEW', [], [['r3', 6], ['r2', 5]]), group('p4-g1', 4, 'ORPHAN')],
  ledger: [],
  tieout: {
    loads_vs_topups: { statement: 0, ledger: 0, diff: 0 },
    atm_vs_withdrawals: { statement: 0, ledger: 0, diff: 0 },
    purchases_vs_rollup: { statement: 0, ledger: 0, diff: 0, purchases_only: 0, rollup_codes: [] },
  },
};

describe('statusMeta', () => {
  test('maps every matcher status to a word, glyph and tone', () => {
    expect(statusMeta('MATCHED')).toEqual({ word: 'Matched', glyph: '✓', tone: 'ok' });
    expect(statusMeta('LINKED')).toEqual({ word: 'Linked', glyph: '✓', tone: 'ok' });
    expect(statusMeta('TIED')).toEqual({ word: 'Tied to ledger', glyph: '✓', tone: 'ok' });
    expect(statusMeta('MISSING_RECEIPT')).toEqual({ word: 'Missing receipt', glyph: '✕', tone: 'bad' });
    expect(statusMeta('ORPHAN')).toEqual({ word: 'No card row', glyph: '✕', tone: 'bad' });
    expect(statusMeta('REVIEW')).toEqual({ word: 'Needs a decision', glyph: '?', tone: 'review' });
    expect(statusMeta('UNEXPLAINED')).toEqual({ word: 'Not in ledger', glyph: '!', tone: 'warn' });
    expect(statusMeta('AMOUNT_MISMATCH')).toEqual({ word: 'Amounts differ', glyph: '!', tone: 'warn' });
    expect(statusMeta('OTHER_MONTH')).toEqual({ word: 'Another month', glyph: '!', tone: 'warn' });
    expect(statusMeta('ROLLUP')).toEqual({ word: 'Roll-up of card spend', glyph: '·', tone: 'muted' });
    expect(statusMeta('NO_CARD_TXN')).toEqual({ word: 'No card transaction', glyph: '!', tone: 'warn' });
  });
  test('falls back to the raw status, and an em dash for null', () => {
    expect(statusMeta('WEIRD')).toEqual({ word: 'WEIRD', glyph: '·', tone: 'muted' });
    expect(statusMeta(null)).toEqual({ word: '—', glyph: '·', tone: 'muted' });
  });
});

describe('counts, filters and sort', () => {
  test('countByStatus includes ALL', () => {
    expect(countByStatus(REPORT.rows)).toEqual({ ALL: 3, MATCHED: 1, MISSING_RECEIPT: 1, REVIEW: 1 });
    expect(countByStatus(REPORT.receipts)).toEqual({ ALL: 4, LINKED: 2, REVIEW: 1, ORPHAN: 1 });
  });
  test('filterRows by status and by query over merchant, ref and amount', () => {
    expect(filterRows(REPORT.rows, 'ALL', '').map(r => r.ref)).toEqual(['r1', 'r2', 'r3']);
    expect(filterRows(REPORT.rows, 'MATCHED', '').map(r => r.ref)).toEqual(['r1']);
    expect(filterRows(REPORT.rows, 'ALL', 'othaim').map(r => r.ref)).toEqual(['r2']);
    expect(filterRows(REPORT.rows, 'ALL', 'R3').map(r => r.ref)).toEqual(['r3']);
    expect(filterRows(REPORT.rows, 'ALL', '75.5').map(r => r.ref)).toEqual(['r3']);
    expect(filterRows(REPORT.rows, 'REVIEW', 'othaim')).toEqual([]);
  });
  test('filterReceipts', () => {
    expect(filterReceipts(REPORT.receipts, 'REVIEW').map(g => g.id)).toEqual(['p3-g1']);
    expect(filterReceipts(REPORT.receipts, 'ALL')).toHaveLength(4);
  });
  test('sortRows by date (time tiebreak) and by amount, both directions, without mutating', () => {
    const before = REPORT.rows.map(r => r.ref);
    expect(sortRows(REPORT.rows, 'date', 'asc').map(r => r.ref)).toEqual(['r3', 'r2', 'r1']);
    expect(sortRows(REPORT.rows, 'date', 'desc').map(r => r.ref)).toEqual(['r1', 'r2', 'r3']);
    expect(sortRows(REPORT.rows, 'amount', 'asc').map(r => r.ref)).toEqual(['r2', 'r3', 'r1']);
    expect(sortRows(REPORT.rows, 'amount', 'desc').map(r => r.ref)).toEqual(['r1', 'r3', 'r2']);
    expect(REPORT.rows.map(r => r.ref)).toEqual(before);
  });
});

describe('formatting and geometry', () => {
  test('money and pct', () => {
    expect(money(1234.5)).toBe('1,234.50');
    expect(money(0)).toBe('0.00');
    expect(money(null)).toBe('');
    expect(pct(100, 150)).toBe('67%');
    expect(pct(1, 0)).toBe('0%');
  });
  test('boxStyle converts 0-1000 space to percentages', () => {
    expect(boxStyle([100, 100, 500, 900])).toEqual({ left: '10%', top: '10%', width: '40%', height: '80%' });
  });
  test('imageUrl', () => {
    expect(imageUrl('kb-1', 'pages/page-01.png')).toBe('/api/petty-cash/kb-1/pages/page-01.png');
  });
});

describe('paneSources', () => {
  test('a row brings its statement strip, its receipts and its ledger line', () => {
    const s = paneSources(REPORT, { kind: 'row', ref: 'r1', source: 'receipt', index: 1 });
    expect(s?.title).toBe('2026-09-05 · 100.00 · GREEN STAR FUEL');
    expect(s?.statement).toHaveLength(1);
    expect(s?.receipts.map(c => c.group_id)).toEqual(['p1-g1', 'p2-g1']);
    expect(s?.ledger?.cell).toBe('B9');
    expect(s?.index).toBe(1);
  });
  test('a row without receipts or ledger has empty receipts and a null ledger, index defaults to 0', () => {
    const s = paneSources(REPORT, { kind: 'row', ref: 'r3', source: 'statement' });
    expect(s?.receipts).toEqual([]);
    expect(s?.ledger).toBeNull();
    expect(s?.index).toBe(0);
  });
  test('a linked group brings the statement rows it is linked to and their ledger line', () => {
    const s = paneSources(REPORT, { kind: 'receipt', id: 'p1-g1', source: 'receipt' });
    expect(s?.title).toBe('Shop p1-g1 · p1');
    expect(s?.receipts.map(c => c.group_id)).toEqual(['p1-g1']);
    expect(s?.statement.map(c => c.crop)).toEqual(['crops/stmt-r1.png']);
    expect(s?.ledger?.code).toBe('ROLL');
  });
  test('an undecided group brings its candidate rows in report order', () => {
    const s = paneSources(REPORT, { kind: 'receipt', id: 'p3-g1', source: 'receipt' });
    expect(s?.statement.map(c => c.crop)).toEqual(['crops/stmt-r2.png', 'crops/stmt-r3.png']);
    expect(s?.ledger?.cell).toBe('B9');
  });
  test('an orphan group has no statement or ledger; unknown ids return null', () => {
    const s = paneSources(REPORT, { kind: 'receipt', id: 'p4-g1', source: 'receipt' });
    expect(s?.statement).toEqual([]);
    expect(s?.ledger).toBeNull();
    expect(paneSources(REPORT, { kind: 'row', ref: 'nope', source: 'statement' })).toBeNull();
    expect(paneSources(REPORT, { kind: 'receipt', id: 'nope', source: 'receipt' })).toBeNull();
  });
  test('rowByRef', () => {
    expect(rowByRef(REPORT, 'r2')?.amount).toBe(50);
    expect(rowByRef(REPORT, 'zz')).toBeUndefined();
  });
});
