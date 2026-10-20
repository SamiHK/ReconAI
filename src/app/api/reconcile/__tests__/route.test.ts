import { describe, test, expect, mock, afterEach } from 'bun:test';
import { NextRequest } from 'next/server';

process.env.SESSION_SECRET = 'test-secret-for-reconcile-route';

// Real session helpers (not mocked): mock.module leaks across test FILES in
// bun test (mock.restore() doesn't undo it), so mocking '@/lib/session'
// here would silently break unrelated test files that run in the same
// process. Sealing a real cookie sidesteps that entirely.
const { encryptApiKeySession, getSessionCookieHeader } = await import('@/lib/session');
const SESSION_COOKIE = getSessionCookieHeader(await encryptApiKeySession('docai-key')).split(';')[0];

const FILE_ID_1 = '11111111-1111-1111-1111-111111111111';
const FILE_ID_2 = '22222222-2222-2222-2222-222222222222';

function sseStream(lines: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const line of lines) {
        controller.enqueue(encoder.encode(line));
      }
      controller.close();
    },
  });
}

/** Reads the route's SSE response body into a list of parsed `data:` events. */
async function readEvents(res: Response): Promise<Array<Record<string, unknown>>> {
  const text = await res.text();
  return text
    .split('\n\n')
    .map(chunk => chunk.replace(/^data: /, '').trim())
    .filter(Boolean)
    .map(chunk => JSON.parse(chunk));
}

function mockCommonDeps() {
  mock.module('@/lib/docai-proxy', () => ({
    docaiFetch: async () =>
      new Response(JSON.stringify({ filename: 'Doc.pdf' }), { status: 200 }),
  }));
  mock.module('@/lib/fetch-segments', () => ({
    fetchSegmentsWithRetry: async () => [{ markdown: 'line 1', title: 'body' }],
  }));
}

function buildRequest(modelId: string): NextRequest {
  return new NextRequest('http://localhost:3000/api/reconcile', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      cookie: SESSION_COOKIE,
    },
    body: JSON.stringify({ fileIds: [FILE_ID_1, FILE_ID_2], modelId }),
  });
}

describe('POST /api/reconcile — LLM stream robustness', () => {
  afterEach(() => {
    mock.restore();
    delete process.env.GEMINI_API_KEY;
  });

  test('stream ends without ever sending a finish_reason → clear dropped-connection error, not a JSON parse failure', async () => {
    mockCommonDeps();
    process.env.GEMINI_API_KEY = 'test-gemini-key';

    const originalFetch = globalThis.fetch;
    globalThis.fetch = mock((url: string) => {
      if (typeof url === 'string' && url.includes('generativelanguage.googleapis.com')) {
        // Server streams a bit of valid content, then the connection is cut —
        // no finish_reason chunk, no [DONE], just EOF. Simulates the provider
        // dropping the connection mid-generation under load.
        return Promise.resolve(
          new Response(
            sseStream([
              'data: {"choices":[{"delta":{"content":"{\\"documentClassifications\\":"}}]}\n\n',
            ]),
            { status: 200, headers: { 'Content-Type': 'text/event-stream' } }
          )
        );
      }
      return originalFetch(url as never);
    }) as typeof globalThis.fetch;

    try {
      const { POST } = await import('../route');
      const res = await POST(buildRequest('gemini/gemini-flash-latest'));
      const events = await readEvents(res);
      const errorEvent = events.find(e => e.type === 'error');

      expect(errorEvent).toBeTruthy();
      expect(String(errorEvent?.message)).not.toContain('Failed to parse LLM response as JSON');
      expect(String(errorEvent?.message).toLowerCase()).toContain('connection');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  test('mid-stream error chunk → surfaces that error immediately instead of continuing', async () => {
    mockCommonDeps();
    process.env.GEMINI_API_KEY = 'test-gemini-key';

    const originalFetch = globalThis.fetch;
    globalThis.fetch = mock((url: string) => {
      if (typeof url === 'string' && url.includes('generativelanguage.googleapis.com')) {
        return Promise.resolve(
          new Response(
            sseStream([
              'data: {"choices":[{"delta":{"content":"{\\"documentClassifications\\":"}}]}\n\n',
              'data: {"error":{"code":503,"message":"model is overloaded","status":"UNAVAILABLE"}}\n\n',
            ]),
            { status: 200, headers: { 'Content-Type': 'text/event-stream' } }
          )
        );
      }
      return originalFetch(url as never);
    }) as typeof globalThis.fetch;

    try {
      const { POST } = await import('../route');
      const res = await POST(buildRequest('gemini/gemini-flash-latest'));
      const events = await readEvents(res);
      const errorEvent = events.find(e => e.type === 'error');

      expect(errorEvent).toBeTruthy();
      expect(String(errorEvent?.message)).toContain('model is overloaded');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });
});

/** Encodes Responses API events the way OpenAI streams them (event + data lines). */
function responsesEvents(events: Array<Record<string, unknown>>): string[] {
  return events.map(e => `event: ${e.type}\ndata: ${JSON.stringify(e)}\n\n`);
}

describe('POST /api/reconcile — OpenAI (Responses API)', () => {
  afterEach(() => {
    mock.restore();
    delete process.env.OPENAI_API_KEY;
  });

  function mockOpenAI(events: Array<Record<string, unknown>>) {
    const calls: Array<{ url: string; init?: RequestInit }> = [];
    const originalFetch = globalThis.fetch;
    globalThis.fetch = mock((url: string, init?: RequestInit) => {
      if (typeof url === 'string' && url.includes('api.openai.com')) {
        calls.push({ url, init });
        return Promise.resolve(
          new Response(sseStream(responsesEvents(events)), {
            status: 200,
            headers: { 'Content-Type': 'text/event-stream' },
          })
        );
      }
      return originalFetch(url as never, init);
    }) as typeof globalThis.fetch;
    return { calls, restore: () => { globalThis.fetch = originalFetch; } };
  }

  test('streams reasoning summaries as thinking events, with high effort and no output cap', async () => {
    mockCommonDeps();
    process.env.OPENAI_API_KEY = 'sk-test-openai';
    const { calls, restore } = mockOpenAI([
      { type: 'response.created' },
      { type: 'response.reasoning_summary_part.added', summary_index: 0 },
      { type: 'response.reasoning_summary_text.delta', delta: 'Comparing the invoice ' },
      { type: 'response.reasoning_summary_text.delta', delta: 'against the PO.' },
      { type: 'response.output_text.delta', delta: '{"documentClassifications":' },
      { type: 'response.completed', response: { status: 'completed' } },
    ]);

    try {
      const { POST } = await import('../route');
      const res = await POST(buildRequest('openai/gpt-5.6-luna'));
      const events = await readEvents(res);

      const thinking = events.filter(e => e.type === 'thinking').map(e => e.text).join('');
      expect(thinking).toBe('Comparing the invoice against the PO.');
      // "against" in the summary lights the compare stage; content lights the report stage.
      expect(events.some(e => e.type === 'stage' && e.stage === 'reasoning-2')).toBe(true);
      expect(events.some(e => e.type === 'stage' && e.stage === 'reasoning-6')).toBe(true);

      expect(calls).toHaveLength(1);
      expect(calls[0].url).toBe('https://api.openai.com/v1/responses');
      const headers = calls[0].init?.headers as Record<string, string>;
      expect(headers['Authorization']).toBe('Bearer sk-test-openai');
      const body = JSON.parse(String(calls[0].init?.body));
      expect(body.model).toBe('gpt-5.6-luna');
      expect(body.reasoning).toEqual({ effort: 'high', summary: 'auto' });
      expect(body).not.toHaveProperty('max_output_tokens');
      expect(body).not.toHaveProperty('temperature');
    } finally {
      restore();
    }
  });

  test('response.incomplete at the output limit → explicit token-limit error', async () => {
    mockCommonDeps();
    process.env.OPENAI_API_KEY = 'sk-test-openai';
    const { restore } = mockOpenAI([
      { type: 'response.output_text.delta', delta: '{"documentClassifications":' },
      { type: 'response.incomplete', response: { incomplete_details: { reason: 'max_output_tokens' } } },
    ]);

    try {
      const { POST } = await import('../route');
      const events = await readEvents(await POST(buildRequest('openai/gpt-5.6-luna')));
      const errorEvent = events.find(e => e.type === 'error');
      expect(String(errorEvent?.message)).toContain('output-token limit');
    } finally {
      restore();
    }
  });

  test('response.failed mid-stream → surfaces the provider message', async () => {
    mockCommonDeps();
    process.env.OPENAI_API_KEY = 'sk-test-openai';
    const { restore } = mockOpenAI([
      { type: 'response.reasoning_summary_text.delta', delta: 'Thinking' },
      { type: 'response.failed', response: { error: { message: 'server_error: try again' } } },
    ]);

    try {
      const { POST } = await import('../route');
      const events = await readEvents(await POST(buildRequest('openai/gpt-5.6-luna')));
      const errorEvent = events.find(e => e.type === 'error');
      expect(String(errorEvent?.message)).toContain('server_error: try again');
    } finally {
      restore();
    }
  });

  test('missing OPENAI_API_KEY → 500 naming the variable, before any upstream call', async () => {
    mockCommonDeps();
    delete process.env.OPENAI_API_KEY;
    const { calls, restore } = mockOpenAI([]);

    try {
      const { POST } = await import('../route');
      const res = await POST(buildRequest('openai/gpt-5.6-luna'));
      expect(res.status).toBe(500);
      const data = await res.json();
      expect(data.error).toContain('OPENAI_API_KEY');
      expect(calls).toHaveLength(0);
    } finally {
      restore();
    }
  });
});
