'use client';
import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from 'react';
import { boxStyle, type Box } from '@/lib/petty-cash-report';
import { cn } from '@/lib/utils';

export type PageBox = { page: number; box: Box; primary: boolean; label: string };

const DEFAULT_ASPECT = 1.414; // A4 until the image reports its own size
const PADDING = 24; // p-3 on both sides of the scroller

/**
 * DocAI's image-mode page viewer, rebuilt small: every page of the file as a lazy <img> with the cited boxes drawn
 * in 0-1000 space on top, centred on the primary box whenever the citation, zoom or jump signal changes.
 */
export function PageStack({ images, boxes, activeIndex, jumpSignal, zoom, onPageInView }: {
  images: string[];
  boxes: PageBox[];
  activeIndex: number;
  jumpSignal: number;
  zoom: number;
  onPageInView?: (page: number) => void;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const pageRefs = useRef(new Map<number, HTMLDivElement>());
  const rafRef = useRef<number | null>(null);
  const [containerWidth, setContainerWidth] = useState(0);
  const [aspects, setAspects] = useState<Record<number, number>>({});
  const [failed, setFailed] = useState<Record<number, boolean>>({});

  const active = boxes[activeIndex] ?? boxes[0] ?? null;
  const citedPage = active?.page ?? 1;
  const activeKey = active ? `${active.page}:${active.box.join(',')}` : '';
  const citedLoaded = aspects[citedPage] !== undefined;
  const pageWidth = Math.max(200, Math.round((containerWidth - PADDING) * (zoom / 100)));

  // The pane's width drives page width (100% = fit); measured, not assumed, so a resized pane re-fits.
  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const ro = new ResizeObserver(entries => {
      for (const e of entries) setContainerWidth(e.contentRect.width);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Centre the primary box. Offsets are read from the page element, so they are right at every zoom.
  useEffect(() => {
    const scroller = scrollRef.current;
    const pageEl = active ? pageRefs.current.get(active.page) : null;
    if (!scroller || !pageEl || !active) return;
    const [x0, y0, x1, y1] = active.box;
    const top = pageEl.offsetTop + ((y0 + y1) / 2000) * pageEl.offsetHeight - scroller.clientHeight / 2;
    const left = pageEl.offsetLeft + ((x0 + x1) / 2000) * pageEl.offsetWidth - scroller.clientWidth / 2;
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    scroller.scrollTo({ top: Math.max(0, top), left: Math.max(0, left), behavior: reduced ? 'auto' : 'smooth' });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeKey, jumpSignal, zoom, pageWidth, citedLoaded]);

  const trackPageInView = () => {
    if (!onPageInView || rafRef.current !== null) return;
    rafRef.current = requestAnimationFrame(() => {
      rafRef.current = null;
      const scroller = scrollRef.current;
      if (!scroller) return;
      const mid = scroller.scrollTop + scroller.clientHeight / 2;
      for (const [page, el] of pageRefs.current) {
        if (el.offsetTop <= mid && mid < el.offsetTop + el.offsetHeight) {
          onPageInView(page);
          return;
        }
      }
    });
  };

  return (
    <div ref={scrollRef} onScroll={trackPageInView} className="relative h-full overflow-auto bg-muted/40 p-3">
      <div className="flex w-max min-w-full flex-col items-center gap-6">
        {images.map((src, i) => {
          const page = i + 1;
          const aspect = aspects[page] ?? DEFAULT_ASPECT;
          const isCited = page === citedPage;
          const height = Math.round(pageWidth * aspect);
          const pageBoxes = boxes.filter(b => b.page === page);
          return (
            <div
              key={page}
              data-page={page}
              ref={el => {
                if (el) pageRefs.current.set(page, el);
                else pageRefs.current.delete(page);
              }}
              className="relative shrink-0"
              style={{
                width: pageWidth,
                height,
                // Off-screen pages skip layout and image loads; the cited one must load so the centring has a real height.
                contentVisibility: isCited ? 'visible' : 'auto',
                containIntrinsicSize: `auto ${height}px`,
              } as CSSProperties}
            >
              <div className="absolute -top-4 left-0 select-none text-[10px] font-medium text-muted-foreground">{page}</div>
              {failed[page] ? (
                <div className="flex h-full w-full items-center justify-center rounded-sm bg-card text-xs text-muted-foreground ring-1 ring-border">
                  Page image missing
                </div>
              ) : (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={src}
                  alt={`Page ${page}`}
                  loading={isCited ? 'eager' : 'lazy'}
                  decoding="async"
                  className="block h-full w-full rounded-sm bg-white shadow-lg ring-1 ring-black/5"
                  onLoad={e => {
                    const im = e.currentTarget;
                    if (im.naturalWidth) setAspects(a => (a[page] ? a : { ...a, [page]: im.naturalHeight / im.naturalWidth }));
                  }}
                  onError={() => setFailed(f => ({ ...f, [page]: true }))}
                />
              )}
              {pageBoxes.map((b, j) => (
                <div
                  key={j}
                  title={b.label}
                  className={cn('pointer-events-none absolute rounded-sm', b.primary ? 'bg-primary/10 ring-2 ring-primary' : 'bg-primary/5 ring-1 ring-primary/50')}
                  style={boxStyle(b.box)}
                />
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}
