import { describe, test, expect, beforeAll, afterAll } from 'bun:test';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { findFolderForKb, isAllowedReportPath } from '../petty-cash';

const KB = '1cd041cc-d3a8-4c35-bf70-ac4ad8f72c5a';
let data: string;

beforeAll(() => {
  data = mkdtempSync(join(tmpdir(), 'petty-'));
  mkdirSync(join(data, 'abujhd'));
  writeFileSync(join(data, 'abujhd', 'config.json'), JSON.stringify({ kb_id: KB, month: '2026-09' }));
  mkdirSync(join(data, 'other'));
  writeFileSync(join(data, 'other', 'config.json'), JSON.stringify({ kb_id: 'zzz' }));
  mkdirSync(join(data, 'nokb'));
  writeFileSync(join(data, 'nokb', 'config.json'), JSON.stringify({ month: '2026-08' }));
  mkdirSync(join(data, 'broken'));
  writeFileSync(join(data, 'broken', 'config.json'), '{not json');
  writeFileSync(join(data, 'stray.txt'), 'x');
});
afterAll(() => rmSync(data, { recursive: true, force: true }));

describe('findFolderForKb', () => {
  test('returns the folder whose config.json carries the kb_id', () => {
    expect(findFolderForKb(data, KB)).toBe(join(data, 'abujhd'));
  });
  test('ignores folders with another or no kb_id, broken configs, and stray files', () => {
    expect(findFolderForKb(data, 'nope')).toBeNull();
  });
  test('tolerates a missing data dir', () => {
    expect(findFolderForKb(join(data, 'missing'), KB)).toBeNull();
  });
});

describe('isAllowedReportPath', () => {
  test('accepts the three shapes', () => {
    expect(isAllowedReportPath(['report.html'])).toBe(true);
    expect(isAllowedReportPath(['pages', 'page-01.png'])).toBe(true);
    expect(isAllowedReportPath(['crops', 'stmt-624417160330.png'])).toBe(true);
  });
  test('rejects traversal, nesting, other names and extensions', () => {
    expect(isAllowedReportPath(['..', 'config.json'])).toBe(false);
    expect(isAllowedReportPath(['pages', '..', 'config.json'])).toBe(false);
    expect(isAllowedReportPath(['pages', 'a', 'b.png'])).toBe(false);
    expect(isAllowedReportPath(['config.json'])).toBe(false);
    expect(isAllowedReportPath(['pages', 'x.svg'])).toBe(false);
    expect(isAllowedReportPath(['pages', 'a%2f.png'])).toBe(false);
    expect(isAllowedReportPath([])).toBe(false);
  });
});
