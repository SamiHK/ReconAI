import { describe, test, expect } from 'bun:test';
import {
  extractCitationNeedle,
  locateCitation,
  segmentRowBox,
  findTableRow,
  type SegmentLike,
} from '../evidence-utils';

/**
 * Synthetic invoice table shaped like real DocAI output: HTML markdown,
 * 'table-former' cells with page-normalized bboxes, English headers with an
 * Arabic suffix. Rows 0 (header) to 5; values chosen so the middle row (2)
 * differs from the rows the citations target — the old bug highlighted
 * the row at the table's vertical center for every HTML-fragment quote.
 */
const ROWS = [
  ['', 'Code', 'Description', 'Qty الحجم', 'Unit Price الحجم', 'Taxable Amount', 'VAT Rate', 'Total'],
  ['1', 'AB-GLV-01', 'Exam Gloves, Medium (box of 100)', '225', '45.00', '10,125.00', '15%', '11,643.75'],
  ['2', 'AB-SYR-05', 'Syringe 5 ml (box of 100)', '150', '32.00', '4,800.00', '15%', '5,520.00'],
  ['3', 'AB-IVS-20', 'IV Set, 20 drops/ml', '400', '21.00', '8,400.00', '15%', '9,660.00'],
  ['4', 'AB-MSK-3P', 'Face Mask, 3-Ply (box of 50)', '300', '22.00', '6,600.00', '15%', '7,590.00'],
  ['5', 'AB-GZE-10', 'Gauze Swabs 10 x 10 cm', '250', '27.50', '6,875.00', '15%', '7,906.25'],
];
const TOP = 0.36;
const ROW_H = 0.05;
const table: SegmentLike = {
  id: 'p1_e0022',
  title: 'table',
  markdown:
    '<table border="1">' +
    ROWS.map(r => '<tr>' + r.map(c => `<td>${c}</td>`).join('') + '</tr>').join('') +
    '</table>',
  coordinates: { pageNumber: 1, xmin: 65, ymin: TOP * 1000, xmax: 933, ymax: (TOP + ROWS.length * ROW_H) * 1000 },
  cellsSource: 'table-former',
  cells: ROWS.flatMap((r, row) =>
    r.map((text, col) => ({
      row,
      col,
      text,
      isHeader: row === 0,
      bbox: {
        x1: 0.07 + col * 0.11,
        y1: TOP + row * ROW_H + 0.005,
        x2: 0.07 + col * 0.11 + 0.1,
        y2: TOP + (row + 1) * ROW_H - 0.005,
      },
    }))
  ),
};
const header: SegmentLike = {
  id: 'p1_e0003',
  title: 'text',
  markdown: 'Invoice Number INV-2026-0871',
  coordinates: { pageNumber: 1, xmin: 60, ymin: 120, xmax: 400, ymax: 140 },
};
const segments = [header, table];

/** The table row the viewer will highlight for a citation (null if unlocated). */
function highlightedRow(citation: string): number | null {
  const loc = locateCitation(citation, segments);
  if (!loc) return null;
  const box = segmentRowBox(segments, loc);
  if (!box) return null;
  return findTableRow(table, (box.y1 + box.y2) / 2);
}

describe('extractCitationNeedle — HTML markup in quotes', () => {
  test('cell tags become a cell separator, not part of the needle', () => {
    expect(extractCitationNeedle("INV.pdf: row 1: '225</td><td>45.00' [reason: x]")).toBe('225 | 45.00');
  });

  test('leading/trailing and repeated tags collapse to single separators', () => {
    expect(extractCitationNeedle("INV.pdf: row 1: '<td>225</td><td></td><td>45.00</td>'")).toBe('225 | 45.00');
  });
});

describe('locateCitation — HTML-fragment quotes land on their own row', () => {
  test('first data row', () => {
    expect(highlightedRow("INV.pdf: line items table: '225</td><td>45.00' [reason: bills 225 vs 200]")).toBe(1);
  });

  test('third data row', () => {
    expect(highlightedRow("INV.pdf: line items table: '400</td><td>21.00' [reason: 21 vs 18.50]")).toBe(3);
  });

  test('last data row', () => {
    expect(highlightedRow("INV.pdf: line items table: '250</td><td>27.50' [reason: x]")).toBe(5);
  });

  test('three-cell fragment', () => {
    expect(highlightedRow("INV.pdf: line items table: '21.00</td><td>8,400.00</td><td>15%' [reason: x]")).toBe(3);
  });
});

describe('locateCitation — plain quotes against a table', () => {
  test('pipe-separated quote (the format the prompt now shows) → its row', () => {
    expect(highlightedRow("INV.pdf: line items table, row 3: '400 | 21.00' [reason: x]")).toBe(3);
  });

  test('space-joined visible text spanning two cells, no row hint → its row', () => {
    expect(highlightedRow("INV.pdf: line items table: '250 27.50' [reason: x]")).toBe(5);
  });

  test('a value repeated in every row resolves to the row named in the hint', () => {
    expect(highlightedRow("INV.pdf: line items table, row 4: '15%' [reason: VAT rate]")).toBe(4);
  });

  test('single exact cell value still resolves to its row', () => {
    expect(highlightedRow("INV.pdf: line items table: '27.50' [reason: x]")).toBe(5);
  });

  test('a quote spanning two rows is NOT located on the table, rather than guessing the middle row', () => {
    // Previously matched the raw table HTML and returned the whole-table box,
    // which the viewer turned into the middle row (2). Unlocated is honest:
    // the viewer then falls back to searching the PDF text layer.
    expect(locateCitation("INV.pdf: line items table: '45.00 ... 32.00' [reason: x]", segments)).toBeNull();
  });

  test('non-table segments still match by markdown', () => {
    const loc = locateCitation("INV.pdf: header: 'INV-2026-0871' [reason: x]", segments);
    expect(loc?.segmentId).toBe('p1_e0003');
  });
});
