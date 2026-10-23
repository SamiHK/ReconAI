// Petty-cash report folders: data/<client>/ with a config.json whose kb_id names the DocAI workspace.
import { createHash } from 'node:crypto';
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

const ACCESS_TTL_MS = 5 * 60 * 1000;
// ponytail: unbounded Map, one entry per key+workspace; add eviction if this ever serves more than a handful of keys
const accessCache = new Map<string, { ok: boolean; at: number }>();
/** True when the DocAI key can see kbId: the workspace list, cached 5 min per key+kb so a report's hundreds of image requests don't each hit DocAI. Only a parsed 200 is cached; failures return false uncached. */
export async function canAccessKb(kbId: string, apiKey: string, listKbs: () => Promise<Response>): Promise<boolean> {
  const key = `${kbId}:${createHash('sha256').update(apiKey).digest('hex')}`;
  const hit = accessCache.get(key);
  if (hit && Date.now() - hit.at < ACCESS_TTL_MS) return hit.ok;
  let ok: boolean;
  try {
    const res = await listKbs();
    if (!res.ok) return false;
    const body = await res.json();
    ok = Array.isArray(body.knowledge_bases) && body.knowledge_bases.some((k: { id?: string }) => k.id === kbId);
  } catch {
    return false;
  }
  accessCache.set(key, { ok, at: Date.now() });
  return ok;
}
