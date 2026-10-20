import { describe, test, expect } from 'bun:test';
import { htmlTablesToText } from '../table-text';

describe('htmlTablesToText', () => {
  test('converts each row to " | "-separated cells, one row per line', () => {
    const html =
      '<table border="1"><tr><td>Code</td><td>Qty الحجم</td><td>Unit Price</td></tr>' +
      '<tr><td>AB-GLV-01</td><td>225</td><td>45.00</td></tr></table>';
    expect(htmlTablesToText(html)).toBe('Code | Qty الحجم | Unit Price\nAB-GLV-01 | 225 | 45.00');
  });

  test('keeps empty cells so columns stay aligned', () => {
    expect(htmlTablesToText('<table><tr><td></td><td>Code</td></tr><tr><td>1</td><td>X</td></tr></table>'))
      .toBe(' | Code\n1 | X');
  });

  test('handles <th>, attributes, and missing closing tags', () => {
    expect(htmlTablesToText('<table><tr><th scope="col">A<th>B<tr><td colspan="2">C</table>')).toBe('A | B\nC');
  });

  test('strips inline markup inside cells and collapses whitespace', () => {
    expect(htmlTablesToText('<table><tr><td><b>Total</b>\n  due</td><td>1,000.00<br/></td></tr></table>'))
      .toBe('Total due | 1,000.00');
  });

  test('decodes common HTML entities', () => {
    expect(htmlTablesToText('<table><tr><td>A &amp; B</td><td>&quot;x&quot; &#39;y&#39; &lt;z&gt;</td><td>a&nbsp;b</td></tr></table>'))
      .toBe('A & B | "x" \'y\' <z> | a b');
  });

  test('leaves text outside tables untouched and keeps it on its own lines', () => {
    const md = 'Invoice INV-1\n\n<table><tr><td>a</td><td>b</td></tr></table>\n\nTotal 10.00';
    expect(htmlTablesToText(md)).toBe('Invoice INV-1\n\na | b\n\nTotal 10.00');
  });

  test('converts several tables and leaves non-table tags alone', () => {
    const md = '<page_header>H</page_header><table><tr><td>1</td></tr></table>mid<table><tr><td>2</td></tr></table>';
    expect(htmlTablesToText(md)).toBe('<page_header>H</page_header>\n1\nmid\n2');
  });

  test('no tables → identical output', () => {
    expect(htmlTablesToText('plain text <!-- formula-not-decoded -->')).toBe('plain text <!-- formula-not-decoded -->');
  });
});
