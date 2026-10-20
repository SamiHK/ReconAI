import { describe, test, expect } from 'bun:test';
import {
  buildLlmRequest,
  parseModelId,
  parseStreamEvent,
  LlmConfigError,
  SYSTEM_PROMPT,
} from '../llm-providers';

const ENV = {
  OPENAI_API_KEY: 'sk-openai',
  DEEPSEEK_API_KEY: 'sk-deepseek',
  GEMINI_API_KEY: 'gemini-key',
  LM_STUDIO_URL: 'http://localhost:1234',
};

describe('parseModelId', () => {
  test('splits provider prefix from model name', () => {
    expect(parseModelId('openai/gpt-5.6-luna')).toEqual({ provider: 'openai', modelName: 'gpt-5.6-luna' });
    expect(parseModelId('deepseek/deepseek-v4-flash')).toEqual({ provider: 'deepseek', modelName: 'deepseek-v4-flash' });
  });

  test('LM Studio keeps the full path after the prefix', () => {
    expect(parseModelId('lmstudio/qwen/qwen3-vl-30b')).toEqual({ provider: 'lmstudio', modelName: 'qwen/qwen3-vl-30b' });
  });

  test('no prefix defaults to lmstudio', () => {
    expect(parseModelId('qwen3')).toEqual({ provider: 'lmstudio', modelName: 'qwen3' });
  });
});

describe('buildLlmRequest — OpenAI', () => {
  const req = buildLlmRequest('openai', 'gpt-5.6-luna', ENV);
  const body = req.buildBody('PROMPT');

  test('uses the Responses API with the OpenAI key', () => {
    expect(req.url).toBe('https://api.openai.com/v1/responses');
    expect(req.headers['Authorization']).toBe('Bearer sk-openai');
  });

  test('requests high reasoning effort with streamed summaries', () => {
    expect(body.reasoning).toEqual({ effort: 'high', summary: 'auto' });
    expect(body.stream).toBe(true);
  });

  test('sends no output cap, so reasoning cannot crowd out the JSON', () => {
    expect(body).not.toHaveProperty('max_output_tokens');
    expect(body).not.toHaveProperty('max_completion_tokens');
    expect(body).not.toHaveProperty('max_tokens');
  });

  test('omits temperature, which reasoning models reject', () => {
    expect(body).not.toHaveProperty('temperature');
  });

  test('passes the system prompt as instructions and the prompt as input', () => {
    expect(body.instructions).toBe(SYSTEM_PROMPT);
    expect(body.input).toBe('PROMPT');
    expect(body).not.toHaveProperty('messages');
  });
});

describe('buildLlmRequest — Chat Completions providers', () => {
  test('DeepSeek: chat endpoint, thinking enabled, high effort', () => {
    const req = buildLlmRequest('deepseek', 'deepseek-v4-flash', ENV);
    const body = req.buildBody('P');
    expect(req.url).toBe('https://api.deepseek.com/v1/chat/completions');
    expect(req.headers['Authorization']).toBe('Bearer sk-deepseek');
    expect(body.thinking).toEqual({ type: 'enabled' });
    expect(body.reasoning_effort).toBe('high');
    expect(body.max_tokens).toBe(32000);
    expect(body.temperature).toBe(0.1);
  });

  test('Gemini: OpenAI-compatible endpoint with the Gemini key', () => {
    const req = buildLlmRequest('gemini', 'gemini-flash-latest', ENV);
    expect(req.url).toBe('https://generativelanguage.googleapis.com/v1beta/openai/chat/completions');
    expect(req.headers['Authorization']).toBe('Bearer gemini-key');
  });

  test('LM Studio: local URL, no auth header, high effort', () => {
    const req = buildLlmRequest('lmstudio', 'qwen/qwen3-vl-30b', ENV);
    expect(req.url).toBe('http://localhost:1234/v1/chat/completions');
    expect(req.headers['Authorization']).toBeUndefined();
    expect(req.buildBody('P').reasoning_effort).toBe('high');
  });

  test('chat body carries system + user messages and streams', () => {
    const body = buildLlmRequest('gemini', 'g', ENV).buildBody('P');
    expect(body.messages).toEqual([
      { role: 'system', content: SYSTEM_PROMPT },
      { role: 'user', content: 'P' },
    ]);
    expect(body.stream).toBe(true);
  });
});

describe('buildLlmRequest — missing configuration', () => {
  test.each([
    ['openai', 'OPENAI_API_KEY'],
    ['deepseek', 'DEEPSEEK_API_KEY'],
    ['gemini', 'GEMINI_API_KEY'],
    ['lmstudio', 'LM_STUDIO_URL'],
  ])('%s without %s throws a clear config error', (provider, varName) => {
    const env = { ...ENV, [varName]: '' };
    expect(() => buildLlmRequest(provider, 'm', env)).toThrow(LlmConfigError);
    expect(() => buildLlmRequest(provider, 'm', env)).toThrow(varName);
  });
});

describe('parseStreamEvent — OpenAI Responses events', () => {
  test('reasoning summary deltas become reasoning text', () => {
    expect(parseStreamEvent('openai', { type: 'response.reasoning_summary_text.delta', delta: 'Comparing' }))
      .toEqual({ reasoning: 'Comparing' });
  });

  test('a second summary part is separated by a blank line; the first is not', () => {
    expect(parseStreamEvent('openai', { type: 'response.reasoning_summary_part.added', summary_index: 0 })).toEqual({});
    expect(parseStreamEvent('openai', { type: 'response.reasoning_summary_part.added', summary_index: 1 }))
      .toEqual({ reasoning: '\n\n' });
  });

  test('output text deltas become content', () => {
    expect(parseStreamEvent('openai', { type: 'response.output_text.delta', delta: '{"a":' }))
      .toEqual({ content: '{"a":' });
  });

  test('completed maps to finish reason stop', () => {
    expect(parseStreamEvent('openai', { type: 'response.completed', response: {} }))
      .toEqual({ finishReason: 'stop' });
  });

  test('incomplete due to the output limit maps to length', () => {
    expect(parseStreamEvent('openai', {
      type: 'response.incomplete',
      response: { incomplete_details: { reason: 'max_output_tokens' } },
    })).toEqual({ finishReason: 'length' });
  });

  test('incomplete for another reason keeps that reason', () => {
    expect(parseStreamEvent('openai', {
      type: 'response.incomplete',
      response: { incomplete_details: { reason: 'content_filter' } },
    })).toEqual({ finishReason: 'content_filter' });
  });

  test('failed and error events surface their message', () => {
    expect(parseStreamEvent('openai', { type: 'response.failed', response: { error: { message: 'boom' } } }))
      .toEqual({ error: 'boom' });
    expect(parseStreamEvent('openai', { type: 'error', message: 'rate limited' }))
      .toEqual({ error: 'rate limited' });
  });

  test('unrelated lifecycle events are ignored', () => {
    expect(parseStreamEvent('openai', { type: 'response.created' })).toEqual({});
    expect(parseStreamEvent('openai', { type: 'response.output_item.added' })).toEqual({});
  });
});

describe('parseStreamEvent — Chat Completions chunks', () => {
  test('reads reasoning_content, content and finish_reason', () => {
    expect(parseStreamEvent('deepseek', {
      choices: [{ delta: { reasoning_content: 'think', content: 'out' }, finish_reason: 'stop' }],
    })).toEqual({ reasoning: 'think', content: 'out', finishReason: 'stop' });
  });

  test('accepts the alternate `reasoning` delta field', () => {
    expect(parseStreamEvent('lmstudio', { choices: [{ delta: { reasoning: 'r' } }] }).reasoning).toBe('r');
  });

  test('a mid-stream error object becomes an error', () => {
    expect(parseStreamEvent('gemini', { error: { message: 'model is overloaded' } }))
      .toEqual({ error: 'model is overloaded' });
  });
});
