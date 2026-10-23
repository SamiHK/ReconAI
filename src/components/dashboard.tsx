'use client';
import { useAuth } from './auth-provider';
import { CreditDisplay } from './credit-display';
import { WorkspaceManager } from './workspace-manager';
import { FileManager } from './file-manager';
import { ReconcileRunner } from './reconcile-runner';
import { Button } from './ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from './ui/dropdown-menu';
import { Separator } from './ui/separator';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import { LogOut, FileText, FileBarChart, Coins, KeyRound, Sun, Moon } from 'lucide-react';
import { useState, type CSSProperties } from 'react';
import { useTheme } from 'next-themes';
import { BrandLogo } from './brand-logo';
import { cn } from '@/lib/utils';

type Tab = 'files' | 'report';

export interface ReconcileRequest {
  fileIds: string[];
  modelId: string;
  nonce: number;
}

export function Dashboard() {
  const { signOut } = useAuth();
  const { resolvedTheme, setTheme } = useTheme();
  const [tab, setTab] = useState<Tab>('files');
  const [selectedKB, setSelectedKB] = useState<string | null>(null);
  const [wsRefreshKey, setWsRefreshKey] = useState(0);
  const [signOutOpen, setSignOutOpen] = useState(false);
  const [reconcileRequest, setReconcileRequest] = useState<ReconcileRequest | null>(null);

  const handleReconcile = (fileIds: string[], modelId: string) => {
    setReconcileRequest({ fileIds, modelId, nonce: Date.now() });
    setTab('report');
  };

  return (
    <div
      className="flex min-h-screen bg-background"
      // --tabbar-h = 0: the sidebar occupies the left, not the top — the
      // report's sticky filter pins flush at the viewport top.
      style={{ '--tabbar-h': '0px' } as CSSProperties}
    >
      {/* Sidebar — sticky full-height rail on the LEFT: logo + vertical
          tabs persist while scrolling. */}
      <aside className="sticky top-0 z-30 flex h-screen w-16 shrink-0 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground md:w-60">
        <div className="flex flex-col gap-1 px-3 pt-6 pb-2 md:px-4">
          <BrandLogo className="hidden md:block" />
          <span className="hidden text-[11px] font-medium uppercase tracking-wide text-muted-foreground md:inline">ReconAI</span>
        </div>
        {selectedKB && (
          <nav className="flex flex-col gap-1 px-2 pt-4 md:px-3" aria-label="Sections">
            {([
              { key: 'files', label: 'Files', Icon: FileText },
              { key: 'report', label: 'Report', Icon: FileBarChart },
            ] as const).map(({ key, label, Icon }) => (
              <button
                key={key}
                type="button"
                aria-label={label}
                title={label}
                aria-current={tab === key ? 'page' : undefined}
                onClick={() => { if (key === 'report') setReconcileRequest(null); setTab(key); }}
                className={cn(
                  'flex h-9 w-full items-center gap-2 rounded-md px-2 text-left text-sm font-medium transition-colors',
                  tab === key ? 'bg-primary text-primary-foreground' : 'text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground'
                )}
              >
                <Icon className="size-4 shrink-0" />
                <span className="hidden md:inline">{label}</span>
              </button>
            ))}
          </nav>
        )}

        {/* Account menu opens upward */}
        <div className="mt-auto px-2 pb-4 md:px-3">
          <DropdownMenu>
            <DropdownMenuTrigger
              render={
                <Button
                  variant="ghost"
                  className="w-full justify-start gap-2 rounded-none px-3 pt-7 pb-6"
                  aria-label="Account menu"
                  title="Account"
                />
              }
            >
              <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
                <KeyRound className="size-4" />
              </span>
              <span className="hidden min-w-0 flex-1 truncate text-left text-sm font-medium text-foreground md:block">
                Account
              </span>
            </DropdownMenuTrigger>
            {/* Cozy popup: credit balance / actions. Every row shares the
                same padding + icon-gutter rhythm; the credits are a plain
                text row (no pill) so nothing sticks out. */}
            <DropdownMenuContent side="top" align="start" className="w-60 p-1.5">
              <div className="flex items-center gap-2.5 rounded-md px-2.5 py-2.5">
                <Coins className="size-4 shrink-0 text-secondary" />
                <span className="text-sm text-foreground">
                  <CreditDisplay />
                </span>
              </div>
              {/* minimal divider above the actions — subtle but visible
                  (bg-foreground/15: the old bg-border hairline vanished on
                  HiDPI) */}
              <Separator className="my-2 bg-foreground/15" />
              <DropdownMenuItem className="py-2.5" onClick={() => signOut()}>
                <KeyRound className="size-4" />
                Change API key
              </DropdownMenuItem>
              <DropdownMenuItem className="py-2.5" onClick={() => setTheme(resolvedTheme === 'dark' ? 'light' : 'dark')}>
                {resolvedTheme === 'dark' ? <Sun className="size-4" /> : <Moon className="size-4" />}
                {resolvedTheme === 'dark' ? 'Light theme' : 'Dark theme'}
              </DropdownMenuItem>
              <DropdownMenuItem
                className="py-2.5 text-destructive data-highlighted:bg-destructive/10 data-highlighted:text-destructive"
                onClick={() => setSignOutOpen(true)}
              >
                <LogOut className="size-4" />
                Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </aside>

      {/* Main column — content scrolls under the sticky rail */}
      <div className="relative min-w-0 flex-1">

      {/* Sign-out confirmation — opened from the account menu; keeps the
          single-click-can't-sign-you-out guarantee */}
      <Dialog open={signOutOpen} onOpenChange={setSignOutOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Sign out of ReconAI?</DialogTitle>
            <DialogDescription>
              This forgets your stored API key on this device. You&apos;ll need to
              enter it again to access your workspaces and reports.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setSignOutOpen(false)}>Cancel</Button>
            <Button
              onClick={() => {
                setSignOutOpen(false);
                signOut();
              }}
            >
              Sign Out
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

        {/* Body — wide cap (1600px) so the PDF preview can use the window on
            desktop; the old max-w-6xl left a big empty right margin when the
            preview was open (user: "padding on a global level") */}
        <div className="mx-auto w-full max-w-[1600px] px-6 py-6">
          {/* Workspace Selection */}
          <section className="mb-8">
            <WorkspaceManager 
              key={wsRefreshKey}
              selectedKB={selectedKB} 
              onSelect={(id) => {
                setReconcileRequest(null); // workspace switch: don't re-run a stale request
                setSelectedKB(id);
              }} 
            />
          </section>

          {selectedKB && (
            <>
              {/* Tabs live in the sidebar rail now (see aside above) */}
              <div key={tab} className="animate-crossfade">
                {tab === 'files' && <FileManager kbId={selectedKB} onWorkspacesChanged={() => setWsRefreshKey(k => k + 1)} onSwitchWorkspace={setSelectedKB} onReconcile={handleReconcile} />}
                {tab === 'report' && <ReconcileRunner key={selectedKB} kbId={selectedKB} reconcileRequest={reconcileRequest} />}
              </div>
            </>
          )}
        </div>

      </div>
    </div>
  );
}
