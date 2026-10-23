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

const ACCESS_TTL_MS = 5 * 60 * 1000;
const accessCache = new Map<string, { ok: boolean; at: number }>();
/** True when the DocAI key can see kbId: the workspace list, cached 5 min per key+kb so a report's hundreds of image requests don't each hit DocAI. */
export async function canAccessKb(kbId: string, apiKey: string, listKbs: () => Promise<Response>): Promise<boolean> {
  const key = `${kbId}:${apiKey.slice(-8)}`;
  const hit = accessCache.get(key);
  if (hit && Date.now() - hit.at < ACCESS_TTL_MS) return hit.ok;
  let ok = false;
  try {
    const res = await listKbs();
    if (res.ok) {
      const body = await res.json();
      ok = Array.isArray(body.knowledge_bases) && body.knowledge_bases.some((k: { id?: string }) => k.id === kbId);
    }
  } catch {
    ok = false;
  }
  accessCache.set(key, { ok, at: Date.now() });
  return ok;
}
