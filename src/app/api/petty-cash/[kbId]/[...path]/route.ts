// Serves the petty-cash scripts' report.html and its images for the workspace whose data/<client>/config.json
// carries that kb_id. Read-only, allowlisted paths, same session gate as the DocAI proxy.
import { NextRequest, NextResponse } from 'next/server';
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { resolveApiKey, COOKIE_NAME } from '@/lib/session';
import { findFolderForKb, isAllowedReportPath } from '@/lib/petty-cash';

const DATA_DIR = join(process.cwd(), 'data');

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ kbId: string; path: string[] }> }
) {
  const apiKey = await resolveApiKey(req.cookies.get(COOKIE_NAME)?.value);
  if (!apiKey) return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });

  const { kbId, path } = await params;
  if (!/^[0-9a-fA-F-]{36}$/.test(kbId) || !isAllowedReportPath(path)) {
    return NextResponse.json({ error: 'Not found' }, { status: 404 });
  }
  const folder = findFolderForKb(DATA_DIR, kbId);
  const file = folder && join(folder, ...path);
  if (!file || !existsSync(file)) return NextResponse.json({ error: 'Not found' }, { status: 404 });

  const html = path[path.length - 1].endsWith('.html');
  return new Response(readFileSync(file), {
    headers: {
      'Content-Type': html ? 'text/html; charset=utf-8' : 'image/png',
      'Cache-Control': 'no-store',
    },
  });
}
