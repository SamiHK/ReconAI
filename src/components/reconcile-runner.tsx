'use client';
import { useEffect, useRef, useState, useSyncExternalStore } from 'react';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { ReportViewer } from './report-viewer';
import { ReconciliationReport } from '@/engine/reconcile';
import { getRunState, setRunState, subscribeRunState, EMPTY_RUN_STATE } from '@/lib/run-store';
import type { ReconcileRequest } from './dashboard';
import AgentPlan, { Task } from './ui/agent-plan';
import { PettyCashReport } from './petty-cash/report';

// Deterministic reconcile pipeline stages. The LLM only emits raw reasoning
// text — WE define the stages; the streamed thinking is attached to the
// active "LLM reasoning" subtask. Retrieval completes server-side before the
// stream starts, so it renders as done from the first frame.
const RECONCILE_SYNONYMS = [
  'Reconciling',
  'Cross-checking',
  'Comparing',
  'Matching',
  'Verifying',
  'Balancing',
  'Aligning',
  'Settling',
];

function buildPlanTasks(thinkingText: string): Task[] {
  return [
    {
      id: 'retrieval',
      title: 'Document Retrieval',
      description: 'Fetch metadata and segments for all selected files',
      status: 'completed',
      priority: 'high',
      level: 0,
      dependencies: [],
      subtasks: [
        { id: 'retrieval-1', title: 'Fetch file metadata', description: '', status: 'completed', priority: 'high' },
        { id: 'retrieval-2', title: 'Fetch document segments', description: '', status: 'completed', priority: 'high' },
      ],
    },
    {
      id: 'reasoning',
      title: 'Reconciliation',
      description: 'Model cross-checks documents, derives figures, and flags discrepancies',
      status: 'in-progress',
      priority: 'high',
      level: 0,
      dependencies: [],
      subtasks: [
        {
          id: 'reasoning-1',
          title: 'Analyzing documents',
          description: thinkingText || 'Waiting for model output…',
          status: 'in-progress',
          priority: 'high',
        },
        { id: 'reasoning-2', title: 'Comparing line items across documents', description: '', status: 'pending', priority: 'high' },
        { id: 'reasoning-3', title: 'Computing billed vs payable totals', description: '', status: 'pending', priority: 'high' },
        { id: 'reasoning-4', title: 'Flagging discrepancies', description: '', status: 'pending', priority: 'medium' },
        { id: 'reasoning-5', title: 'Summarizing findings', description: '', status: 'pending', priority: 'medium' },
        { id: 'reasoning-6', title: 'Preparing report', description: '', status: 'pending', priority: 'medium' },
      ],
    },
    {
      id: 'report',
      title: 'Report Generation',
      description: 'Validate output and persist the reconciliation report',
      status: 'pending',
      priority: 'medium',
      level: 0,
      dependencies: [],
      subtasks: [
        { id: 'report-1', title: 'Parsing model output', description: '', status: 'pending', priority: 'medium' },
        { id: 'report-2', title: 'Saving report', description: '', status: 'pending', priority: 'medium' },
      ],
    },
  ];
}

// Mark the currently in-progress reasoning subtask as failed so the plan
// shows exactly where the run stopped (the plan renders 'failed' with a
// red X icon). No-op when nothing is in-progress.
function failActiveSubtask(plan: Task[] | null): Task[] | null {
  if (!plan) return plan;
  return plan.map(t => {
    if (t.id !== 'reasoning') return t;
    const idx = t.subtasks.findIndex(s => s.status === 'in-progress');
    if (idx === -1) return t;
    return {
      ...t,
      subtasks: t.subtasks.map((s, i) => (i === idx ? { ...s, status: 'failed' } : s)),
    };
  });
}

export function ReconcileRunner({ kbId, reconcileRequest }: {
  kbId: string;
  reconcileRequest: ReconcileRequest | null;
}) {
  // Live run state lives in the module-level store (per kbId) so a run
  // survives tab/workspace switches: remounting re-attaches to the same
  // thinking logs / plan / report instead of starting from a blank slate.
  const runState = useSyncExternalStore(
    subscribeRunState,
    () => getRunState(kbId),
    () => EMPTY_RUN_STATE,
  );
  const { running, error, report, planTasks, thinkingOpen } = runState;
  const [synonymIdx, setSynonymIdx] = useState(0);
  const lastNonce = useRef(0);

  // Rotate the header synonym while a run is in progress
  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => {
      setSynonymIdx(i => (i + 1) % RECONCILE_SYNONYMS.length);
    }, 3000);
    return () => clearInterval(id);
  }, [running]);

  const run = async (fileIds: string[], requestedModelId: string, runKbId: string) => {
    if (fileIds.length < 2) {
      setRunState(runKbId, s => ({ ...s, error: 'Need at least 2 parsed documents to reconcile.' }));
      return;
    }
    setRunState(runKbId, s => ({
      ...s,
      running: true,
      error: '',
      report: null,
      planTasks: buildPlanTasks(''),
      thinkingOpen: true, // auto-open while streaming
    }));

    try {
      // Model comes from the Files tab selector; fall back to DeepSeek V4 Flash.
      let modelId = requestedModelId;
      if (!modelId) modelId = 'deepseek/deepseek-v4-flash';

      const res = await fetch('/api/reconcile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fileIds, modelId }),
      });

      const contentType = res.headers.get('content-type') || '';
      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
        throw new Error(err.error || 'Reconciliation failed');
      }

      if (!contentType.includes('text/event-stream')) {
        // Legacy path: plain JSON response
        const data = await res.json();
        const r = data.report;
        if (!r) throw new Error('Reconciliation returned no report');
        setRunState(runKbId, s => ({ ...s, report: r }));
        return;
      }

      // SSE stream: live LLM thinking logs, then the final report
      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split('\n\n');
        buffer = events.pop() || '';

        for (const evt of events) {
          const line = evt.split('\n').find(l => l.startsWith('data: '));
          if (!line) continue;
          let msg: { type?: string; text?: string; stage?: string; chars?: number; report?: ReconciliationReport; message?: string };
          try {
            msg = JSON.parse(line.slice(6));
          } catch {
            continue;
          }
          if (msg.type === 'stage' && msg.stage) {
            // Light up the matching subtask: mark all subtasks up to and
            // including `stage` as completed except the stage itself, which
            // stays in-progress until the next stage fires (or the report lands)
            setRunState(runKbId, s => {
              if (!s.planTasks) return s;
              return {
                ...s,
                planTasks: s.planTasks.map(t => {
                  if (t.id !== 'reasoning') return t;
                  const targetIdx = t.subtasks.findIndex(su => su.id === msg.stage);
                  if (targetIdx === -1) return t;
                  return {
                    ...t,
                    subtasks: t.subtasks.map((su, i) => i < targetIdx
                      ? { ...su, status: 'completed' }
                      : i === targetIdx
                        ? { ...su, status: 'in-progress' }
                        : su),
                  };
                }),
              };
            });
          } else if (msg.type === 'thinking' && msg.text) {
            // Append the streamed text to the subtask that is CURRENTLY
            // in-progress (follows the stage events), not always the first
            // one. Do NOT rebuild the plan, or per-step stage progress
            // would be wiped on every chunk.
            setRunState(runKbId, s => {
              if (!s.planTasks) return s;
              const reason = s.planTasks.find(t => t.id === 'reasoning');
              if (!reason) return s;
              const activeIdx = reason.subtasks.findIndex(su => su.status === 'in-progress');
              const targetIdx = activeIdx === -1 ? 0 : activeIdx;
              const old = reason.subtasks[targetIdx]?.description || '';
              const next = old === 'Waiting for model output…' ? msg.text! : old + msg.text!;
              return {
                ...s,
                planTasks: s.planTasks.map(t => t.id !== 'reasoning' ? t : {
                  ...t,
                  subtasks: t.subtasks.map((su, i) => i === targetIdx
                    ? { ...su, description: next.slice(-8000) }
                    : su),
                }),
              };
            });
          } else if (msg.type === 'progress' && typeof msg.chars === 'number') {
            // Live character count while the model writes the report —
            // keeps the final "Preparing report" stage visibly moving
            setRunState(runKbId, s => {
              if (!s.planTasks) return s;
              return {
                ...s,
                planTasks: s.planTasks.map(t => t.id !== 'reasoning' ? t : {
                  ...t,
                  subtasks: t.subtasks.map((su, i) => i === 5
                    ? { ...su, description: `Writing report JSON… ${msg.chars!.toLocaleString()} chars` }
                    : su),
                }),
              };
            });
          } else if (msg.type === 'report' && msg.report) {
            const finishedReport = msg.report; // narrow for the closure
            setRunState(runKbId, s => ({
              ...s,
              report: finishedReport,
              planTasks: s.planTasks
                ? s.planTasks.map(t => t.id === 'reasoning' || t.id === 'report'
                    ? { ...t, status: 'completed', subtasks: t.subtasks.map(su => ({ ...su, status: 'completed' })) }
                    : t)
                : s.planTasks,
            }));
          } else if (msg.type === 'error') {
            throw new Error(msg.message || 'Reconciliation failed');
          }
        }
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Reconciliation failed';
      setRunState(runKbId, s => ({
        ...s,
        error: message,
        running: false,
        // Show where the run stopped: mark the in-progress subtask as failed
        // (the plan renders 'failed' with a red X) — a frozen-looking plan
        // with a plain error banner made failures hard to read.
        planTasks: failActiveSubtask(s.planTasks),
      }));
    } finally {
      setRunState(runKbId, s => ({ ...s, running: false, thinkingOpen: false })); // collapse when done — report starts at KPIs
    }
  };

  const [pettyCashUrl, setPettyCashUrl] = useState<string | null>(null);
  const [showPettyCash, setShowPettyCash] = useState(false);
  const [pettyRun, setPettyRun] = useState<{ busy: boolean; note: string | null; error: string | null; version: number }>({ busy: false, note: null, error: null, version: 0 });

  // Re-run the matcher and report on the server, then reload the pane (a new version makes the report re-fetch report.json).
  const runPettyCash = async () => {
    setPettyRun(s => ({ ...s, busy: true, note: null, error: null }));
    try {
      const res = await fetch(`/api/petty-cash/${kbId}/run`, { method: 'POST' });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error || 'Run failed');
      const r = body.rows || {};
      const note = `Matched ${r.MATCHED ?? 0} · Needs a decision ${r.REVIEW ?? 0} · Missing receipt ${r.MISSING_RECEIPT ?? 0} · ${(body.durationMs / 1000).toFixed(1)}s`;
      setPettyRun(s => ({ busy: false, note, error: null, version: s.version + 1 }));
      setShowPettyCash(true);
    } catch (e) {
      setPettyRun(s => ({ ...s, busy: false, error: e instanceof Error ? e.message : 'Run failed' }));
    }
  };
  // One probe per workspace: a 200 means the scripts' report.json exists for this kbId.
  useEffect(() => {
    const url = `/api/petty-cash/${kbId}/report.json`;
    let cancelled = false;   // no reset needed: the runner is remounted per workspace (key={kbId})
    fetch(url, { method: 'HEAD' })
      .then(r => { if (!cancelled && r.ok) setPettyCashUrl(url); })
      .catch(() => { /* no pill */ });
    return () => { cancelled = true; };
  }, [kbId]);

  // Auto-run when a reconcile request arrives from the Files tab.
  // kbId never changes within a mount (runner is remounted per workspace
  // via key={kbId}), so it's safe as a dependency.
  useEffect(() => {
    if (!reconcileRequest || reconcileRequest.nonce === lastNonce.current) return;
    lastNonce.current = reconcileRequest.nonce;
    run(reconcileRequest.fileIds, reconcileRequest.modelId, kbId);
  }, [reconcileRequest, kbId]);

  return (
    <div>
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="text-h3">Report</h2>
        {pettyCashUrl && (
          <div className="flex items-center gap-2">
            {pettyRun.note && <span className="text-xs text-muted-foreground">{pettyRun.note}</span>}
            {pettyRun.error && <span className="text-xs text-destructive">{pettyRun.error}</span>}
            <Button size="sm" onClick={runPettyCash} disabled={pettyRun.busy} aria-busy={pettyRun.busy}>
              {pettyRun.busy ? 'Running…' : 'Run petty-cash reconciliation'}
            </Button>
            <button
              type="button"
              onClick={() => setShowPettyCash(v => !v)}
              className="rounded-md border border-border px-3 py-1 text-xs text-muted-foreground hover:text-foreground"
            >
              {showPettyCash ? 'Back to reconciliation' : 'Petty-cash report'}
            </button>
          </div>
        )}
      </div>
      {showPettyCash && pettyCashUrl ? (
        <PettyCashReport kbId={kbId} version={pettyRun.version} />
      ) : (
        <>

      {/* Live reconcile pipeline (streamed during reconciliation) */}
      {(running || planTasks) && (
        <details className="group mb-8" open={thinkingOpen} onToggle={e => setRunState(kbId, s => ({ ...s, thinkingOpen: (e.target as HTMLDetailsElement).open }))}>
          <summary className="cursor-pointer text-h3 mb-2 flex items-center gap-2 select-none">
            <span className="text-xs text-muted-foreground transition-transform group-open:rotate-90">▶</span>
            {running ? (
              <span className="inline-flex items-center gap-2" aria-live="polite">
                <span className="w-2 h-2 rounded-full bg-foreground animate-pulse" aria-label="working" />
                <span key={synonymIdx} className="animate-fade-up inline-block">
                  {RECONCILE_SYNONYMS[synonymIdx]}<span className="animate-pulse">…</span>
                </span>
              </span>
            ) : (
              'Reconcile Progress'
            )}
          </summary>
          {planTasks && (
            <AgentPlan tasks={planTasks} defaultExpanded={['reasoning']} />
          )}
          {!running && (
            <p className="mt-3 text-xs text-muted-foreground">
              Model: {reconcileRequest?.modelId || 'auto'}
            </p>
          )}
        </details>
      )}

      {error && (
        <Card className="p-6 mb-6">
          <p className="text-sm text-destructive">{error}</p>
        </Card>
      )}

      {report ? (
        <ReportViewer report={report} />
      ) : (
        !running && !error && (
          <Card className="p-6">
            <p className="text-sm text-muted-foreground">
              No report yet. Select 2+ parsed files in the Files tab and click{" "}
              <strong>Reconcile</strong> at least two parsed files to build a report here.
            </p>
          </Card>
        )
      )}
        </>
      )}
    </div>
  );
}
