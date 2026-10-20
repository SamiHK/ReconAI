/**
 * Converts DocAI's HTML tables into plain text rows for the LLM prompt.
 *
 * DocAI segment markdown carries tables as raw HTML
 * (`<table><tr><td>225</td><td>45.00</td>...`). Passed through unchanged,
 * the model is told to quote "exact characters" and so quotes markup
 * ('225</td><td>45.00'), which the evidence viewer cannot pin to a row.
 * Plain rows ("1 | AB-GLV-01 | 225 | 45.00") keep every visible character
 * and the column structure, and leave nothing but real document text to quote.
 *
 * Only <table> blocks are rewritten; all other text is returned unchanged.
 * Entities are decoded here, so callers must apply any prompt-framing
 * neutralization (e.g. of `</document`) AFTER this conversion.
 */

const TABLE_RE = /<table\b[^>]*>([\s\S]*?)(?:<\/table\s*>|$)/gi;
const ROW_SPLIT_RE = /<tr\b[^>]*>/i;
// A cell runs from its opening tag to the next cell/row boundary, so missing
// closing tags (common in OCR'd HTML) still split correctly.
const CELL_RE = /<t[dh]\b[^>]*>([\s\S]*?)(?=<t[dh]\b|<\/tr|<\/table|$)/gi;

const NAMED_ENTITIES: Record<string, string> = {
  amp: '&',
  lt: '<',
  gt: '>',
  quot: '"',
  apos: "'",
  nbsp: ' ',
};

export function decodeHtmlEntities(text: string): string {
  return text.replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (match, ent: string) => {
    if (ent[0] === '#') {
      const code = ent[1] === 'x' || ent[1] === 'X' ? parseInt(ent.slice(2), 16) : parseInt(ent.slice(1), 10);
      return Number.isFinite(code) && code > 0 && code <= 0x10ffff ? String.fromCodePoint(code) : match;
    }
    return NAMED_ENTITIES[ent.toLowerCase()] ?? match;
  });
}

function cellText(html: string): string {
  return decodeHtmlEntities(html.replace(/<[^>]*>/g, ' '))
    .replace(/\s+/g, ' ')
    .trim();
}

function tableToRows(inner: string): string[] {
  return inner
    .split(ROW_SPLIT_RE)
    .map(rowHtml => [...rowHtml.matchAll(CELL_RE)].map(m => cellText(m[1])))
    .filter(cells => cells.length > 0)
    .map(cells => cells.join(' | '));
}

/** Rewrites every HTML table in `text` as newline-separated " | " rows. */
export function htmlTablesToText(text: string): string {
  return text.replace(TABLE_RE, (match: string, inner: string, offset: number, whole: string) => {
    const end = offset + match.length;
    // Keep the table on its own lines when it is glued to surrounding text.
    const before = offset > 0 && whole[offset - 1] !== '\n' ? '\n' : '';
    const after = end < whole.length && whole[end] !== '\n' ? '\n' : '';
    return before + tableToRows(inner).join('\n') + after;
  });
}
