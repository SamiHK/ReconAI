// Petty-cash report folders: data/<client>/ with a config.json whose kb_id names the DocAI workspace.
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

const PLAIN = /^[A-Za-z0-9_.-]+$/;

/** First data/<client>/ whose config.json has kb_id === kbId, else null. Missing dir and bad JSON are "no match". */
export function findFolderForKb(dataDir: string, kbId: string): string | null {
  if (!existsSync(dataDir)) return null;
  for (const name of readdirSync(dataDir).sort()) {
    const dir = join(dataDir, name);
    const cfg = join(dir, 'config.json');
    if (!statSync(dir).isDirectory() || !existsSync(cfg)) continue;
    try {
      if (JSON.parse(readFileSync(cfg, 'utf8')).kb_id === kbId) return dir;
    } catch {
      /* not this one */
    }
  }
  return null;
}

/** report.html | pages/<name>.png | crops/<name>.png, every segment plain-safe (no '..', no '%', no '/'). */
export function isAllowedReportPath(segments: string[]): boolean {
  if (!segments.every(s => PLAIN.test(s) && s !== '..' && s !== '.')) return false;
  if (segments.length === 1) return segments[0] === 'report.html';
  return segments.length === 2 && (segments[0] === 'pages' || segments[0] === 'crops') && segments[1].endsWith('.png');
}
