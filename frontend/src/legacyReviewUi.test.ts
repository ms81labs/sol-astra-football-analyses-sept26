import { readFileSync } from 'node:fs';

// @ts-expect-error jsdom is installed without its optional type package.
import { JSDOM } from 'jsdom';
import { describe, expect, it, vi } from 'vitest';

const metadata = 'source"><img data-legacy-review-injection onerror="window.__legacyMetadataHandlerRan = true">';

const reviewPages = [
  {
    name: 'promoted v6',
    file: '../../backend/review_ui/promoted_v6_manual_review/index.html',
    key: 'sourceClipId',
    state: {
      summary: { pendingReviewCount: 1, reviewItemCount: 1, reviewedPositiveCount: 0, reviewedNegativeCount: 0 },
      reviewItems: [{ decision: 'pending_review', sourceClipId: metadata, reviewItemId: 'review-1', seedBBox: null }],
    },
  },
  {
    name: 'v7.1 positive diversity',
    file: '../../backend/review_ui/v7_1_positive_diversity_review/index.html',
    key: 'sourceClipId',
    state: {
      summary: { pendingReviewItemCount: 1, resolvedReviewItemCount: 0, newReviewedPositiveRowCount: 0, reviewDeferredUnclearCount: 0 },
      reviewItems: [{ reviewStatus: 'pending_review', sourceClipId: metadata, candidateId: 'candidate-1', sourceFrameBbox: null }],
    },
  },
  {
    name: 'SoccerNet detector miss',
    file: '../../backend/review_ui/football_external_soccernet_detector_miss_review/index.html',
    key: 'eventLabel',
    state: {
      summary: { pendingReviewItemCount: 1, resolvedReviewItemCount: 0, reviewedRealDetectorMissPositiveCount: 0, reviewDeferredUnclearCount: 0 },
      reviewItems: [{ reviewStatus: 'pending_review', eventLabel: metadata, reviewItemId: 'review-1', sourceFrameBbox: null }],
    },
  },
];

describe('legacy review metadata', () => {
  it.each(reviewPages)('renders $name metadata as literal text', async ({ file, key, state }) => {
    const dom = new JSDOM(readFileSync(new URL(file, import.meta.url), 'utf8'), {
      runScripts: 'dangerously',
      beforeParse(window: Window & typeof globalThis) {
        Object.defineProperty(window.HTMLCanvasElement.prototype, 'getContext', {
          value: () => ({
            clearRect() {},
            drawImage() {},
            fillRect() {},
            fillText() {},
            restore() {},
            save() {},
            strokeRect() {},
          }),
        });
        window.fetch = async () => ({ ok: true, status: 200, json: async () => state }) as Response;
      },
    });

    try {
      const meta = dom.window.document.getElementById('meta');
      await vi.waitFor(() => expect(meta?.children.length).toBeGreaterThan(0));

      const label = [...meta!.querySelectorAll('dt')].find((element) => element.textContent === key);
      const injectedNode = meta!.querySelector('[data-legacy-review-injection]');
      injectedNode?.dispatchEvent(new dom.window.Event('error'));

      expect(label?.nextElementSibling?.textContent).toBe(metadata);
      expect(injectedNode).toBeNull();
      expect(meta!.querySelector('[onerror]')).toBeNull();
      expect((dom.window as typeof dom.window & { __legacyMetadataHandlerRan?: boolean }).__legacyMetadataHandlerRan).not.toBe(true);
    } finally {
      dom.window.close();
    }
  });
});

function jsonResponse(body: unknown, ok = true): Response {
  return { ok, status: ok ? 200 : 500, json: async () => body } as Response;
}

function reviewStateForPendingTest(page: (typeof reviewPages)[number]) {
  const first = { ...page.state.reviewItems[0] } as Record<string, unknown>;
  const idKey = page.name === 'v7.1 positive diversity' ? 'candidateId' : 'reviewItemId';
  const second = { ...first, [idKey]: 'review-2', reviewerNotes: 'second item', reviewNotes: 'second item' };
  return { ...page.state, reviewItems: [first, second] };
}

function createReviewDom(file: string, fetch: typeof window.fetch) {
  return new JSDOM(readFileSync(new URL(file, import.meta.url), 'utf8'), {
    runScripts: 'dangerously',
    beforeParse(window: Window & typeof globalThis) {
      Object.defineProperty(window.HTMLCanvasElement.prototype, 'getContext', {
        value: () => ({ clearRect() {}, drawImage() {}, fillRect() {}, fillText() {}, restore() {}, save() {}, strokeRect() {} }),
      });
      Object.defineProperty(window.HTMLCanvasElement.prototype, 'getBoundingClientRect', {
        value: () => ({ left: 0, top: 0, width: 100, height: 100 }),
      });
      window.fetch = fetch;
    },
  });
}

function boxedReviewState(page: (typeof reviewPages)[number]) {
  const state = reviewStateForPendingTest(page);
  const box = { x1: 10, y1: 20, x2: 30, y2: 40 };
  for (const item of state.reviewItems as Record<string, unknown>[]) {
    if (page.name === 'promoted v6') item.seedBBox = box;
    else item.sourceFrameBbox = box;
  }
  return { state, box };
}

function saveButton(document: Document, page: (typeof reviewPages)[number]) {
  return document.querySelector<HTMLButtonElement>(page.name === 'promoted v6' ? '[data-decision="adjust_bbox"]' : '[data-status="reviewed_positive_ball"], [data-status="reviewed_real_detector_miss_positive"]')!;
}

function savedBox(body: Record<string, unknown>, page: (typeof reviewPages)[number]) {
  return page.name === 'promoted v6' ? body.reviewedBBox : body.sourceFrameBbox;
}

describe('legacy review pending actions', () => {
  it.each(reviewPages)('keeps $name draft and bbox through pending canvas actions', async (page) => {
    const { state, box } = boxedReviewState(page);
    let rejectSave!: (error: Error) => void;
    const bodies: Record<string, unknown>[] = [];
    const fetchMock = vi.fn<(url: string, init?: RequestInit) => Promise<Response>>((url, init) => {
      if (url === '/api/review-state') return Promise.resolve(jsonResponse(state));
      bodies.push(JSON.parse(String(init?.body)));
      if (bodies.length === 1) return new Promise<Response>((_, reject) => { rejectSave = reject; });
      return Promise.resolve(jsonResponse({}));
    });
    const fetch = fetchMock as unknown as typeof window.fetch;
    const dom = createReviewDom(page.file, fetch);

    try {
      const { document, KeyboardEvent, MouseEvent } = dom.window;
      await vi.waitFor(() => expect(document.getElementById('position')?.textContent).toBe('1 / 2'));
      const notes = document.querySelector<HTMLTextAreaElement>('textarea')!;
      const reason = document.querySelector<HTMLInputElement>('#rejection-reason');
      notes.value = 'draft that must be submitted';
      if (reason) reason.value = 'draft reason';
      saveButton(document, page).click();

      await vi.waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
      const submittedDraft = bodies[0];
      expect(submittedDraft.reviewerNotes ?? submittedDraft.reviewNotes).toBe('draft that must be submitted');
      expect(document.querySelector('main')?.getAttribute('aria-busy')).toBe('true');
      expect([...document.querySelectorAll<HTMLButtonElement | HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>('button, input, select, textarea')].every((control) => control.disabled)).toBe(true);

      document.getElementById('next')!.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      document.getElementById('filter')!.dispatchEvent(new dom.window.Event('change', { bubbles: true }));
      dom.window.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
      dom.window.dispatchEvent(new KeyboardEvent('keydown', { key: 'a', bubbles: true }));
      notes.click();
      notes.dispatchEvent(new KeyboardEvent('keydown', { key: 'x', bubbles: true }));
      reason?.click();
      reason?.dispatchEvent(new KeyboardEvent('keydown', { key: 'x', bubbles: true }));
      document.querySelector<HTMLButtonElement>('[data-reason]')?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      document.querySelector<HTMLInputElement>('#auto-advance')?.click();
      document.querySelector<HTMLCanvasElement>('canvas')!.dispatchEvent(new MouseEvent('mousedown', { clientX: 40, clientY: 40, bubbles: true }));
      dom.window.dispatchEvent(new MouseEvent('mousemove', { clientX: 60, clientY: 60, bubbles: true }));
      expect(document.getElementById('position')?.textContent).toBe('1 / 2');
      expect(notes.value).toBe('draft that must be submitted');
      expect(reason?.value ?? '').toBe(reason ? 'draft reason' : '');
      expect(document.querySelector<HTMLInputElement>('#auto-advance')?.checked ?? true).toBe(true);
      expect(fetch).toHaveBeenCalledTimes(2);

      rejectSave(new Error('network unavailable'));
      await vi.waitFor(() => expect(document.getElementById('status')?.textContent).toMatch(/save failed/i));
      await vi.waitFor(() => expect(document.querySelector('main')?.getAttribute('aria-busy')).toBe('false'));
      expect([...document.querySelectorAll<HTMLButtonElement | HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>('button, input, select, textarea')].some((control) => !control.disabled)).toBe(true);
      saveButton(document, page).click();
      await vi.waitFor(() => expect(bodies).toHaveLength(2));
      expect(savedBox(bodies[1], page)).toEqual(box);
      await vi.waitFor(() => expect(fetch).toHaveBeenCalledTimes(4));
    } finally {
      dom.window.close();
    }
  });

  it.each(['a rejected request', 'invalid response JSON'] as const)('reports %s without replacing the draft', async (failure) => {
    for (const page of reviewPages) {
    const state = reviewStateForPendingTest(page);
    const fetch = vi.fn((url: string) => url === '/api/review-state'
      ? Promise.resolve(jsonResponse(state))
      : failure === 'a rejected request'
        ? Promise.reject(new Error('network unavailable'))
        : Promise.resolve({ ok: true, status: 200, json: async () => { throw new Error('invalid JSON'); } } as unknown as Response)) as unknown as typeof window.fetch;
    const dom = createReviewDom(page.file, fetch);

    try {
      const notes = dom.window.document.querySelector<HTMLTextAreaElement>('textarea')!;
      await vi.waitFor(() => expect(dom.window.document.getElementById('position')?.textContent).toBe('1 / 2'));
      notes.value = 'draft remains visible';
      dom.window.document.querySelector<HTMLButtonElement>('[data-decision], [data-status]')!.click();
      await vi.waitFor(() => expect(dom.window.document.getElementById('status')?.textContent).toMatch(/save failed/i));
      expect(notes.value).toBe('draft remains visible');
      expect(dom.window.document.querySelector('main')?.getAttribute('aria-busy')).toBe('false');
      expect([...dom.window.document.querySelectorAll<HTMLButtonElement | HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>('button, input, select, textarea')].some((control) => !control.disabled)).toBe(true);
    } finally {
      dom.window.close();
    }
    }
  });

  it.each(reviewPages)('allows only one pending $name resolver request', async (page) => {
    const state = reviewStateForPendingTest(page);
    let resolveResolver!: (response: Response) => void;
    const fetch = vi.fn((url: string) => {
      if (url === '/api/review-state') return Promise.resolve(jsonResponse(state));
      return new Promise<Response>((resolve) => { resolveResolver = resolve; });
    }) as unknown as typeof window.fetch;
    const dom = createReviewDom(page.file, fetch);

    try {
      const { document, MouseEvent } = dom.window;
      await vi.waitFor(() => expect(document.getElementById('position')?.textContent).toBe('1 / 2'));
      const resolver = document.getElementById('run-resolution')!;
      resolver.click();
      await vi.waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
      resolver.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      expect(fetch).toHaveBeenCalledTimes(2);
      expect(document.querySelector('main')?.getAttribute('aria-busy')).toBe('true');

      resolveResolver(jsonResponse({ summary: { batchStatus: 'passed' }, nextRecommendedNextLever: 'next' }));
      await vi.waitFor(() => expect(document.querySelector('main')?.getAttribute('aria-busy')).toBe('false'));
      expect(document.getElementById('status')?.textContent).toMatch(/gate:|resolver:/i);
    } finally {
      dom.window.close();
    }
  });

  it.each(['a rejected save', 'a successful save'] as const)('clears stale canvas drag state after %s', async (outcome) => {
    for (const page of reviewPages) {
      const { state, box } = boxedReviewState(page);
      let resolveSave!: (response: Response) => void;
      let rejectSave!: (error: Error) => void;
      const bodies: Record<string, unknown>[] = [];
      const fetch = vi.fn((url: string, init?: RequestInit) => {
        if (url === '/api/review-state') return Promise.resolve(jsonResponse(state));
        bodies.push(JSON.parse(String(init?.body)));
        return new Promise<Response>((resolve, reject) => { resolveSave = resolve; rejectSave = reject; });
      }) as unknown as typeof window.fetch;
      const dom = createReviewDom(page.file, fetch);

      try {
        const { document, KeyboardEvent, MouseEvent } = dom.window;
        await vi.waitFor(() => expect(document.getElementById('position')?.textContent).toBe('1 / 2'));
        document.querySelector<HTMLCanvasElement>('canvas')!.dispatchEvent(new MouseEvent('mousedown', { clientX: 0, clientY: 0, bubbles: true }));
        if (page.name === 'SoccerNet detector miss') saveButton(document, page).click();
        else dom.window.dispatchEvent(new KeyboardEvent('keydown', { key: 'a', bubbles: true }));
        await vi.waitFor(() => expect(bodies).toHaveLength(1));
        dom.window.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));

        if (outcome === 'a rejected save') rejectSave(new Error('network unavailable'));
        else resolveSave(jsonResponse({}));
        await vi.waitFor(() => expect(document.querySelector('main')?.getAttribute('aria-busy')).toBe('false'));
        dom.window.dispatchEvent(new MouseEvent('mousemove', { clientX: 50, clientY: 50, bubbles: true }));
        saveButton(document, page).click();
        await vi.waitFor(() => expect(bodies).toHaveLength(2));
        expect(savedBox(bodies[1], page)).toEqual(page.name === 'SoccerNet detector miss' && outcome === 'a rejected save' ? { x1: 0, y1: 0, x2: 0, y2: 0 } : box);
      } finally {
        dom.window.close();
      }
    }
  });

  it.each(['a rejected reload', 'a non-OK reload', 'invalid reload JSON'] as const)('keeps every page draft and bbox on %s', async (failure) => {
    for (const page of reviewPages) {
      const { state, box } = boxedReviewState(page);
      const bodies: Record<string, unknown>[] = [];
      let stateRequests = 0;
      const fetch = vi.fn((url: string, init?: RequestInit) => {
        if (url !== '/api/review-state') {
          bodies.push(JSON.parse(String(init?.body)));
          return Promise.resolve(jsonResponse({}));
        }
        stateRequests += 1;
        if (stateRequests === 1) return Promise.resolve(jsonResponse(state));
        if (failure === 'a rejected reload') return Promise.reject(new Error('reload unavailable'));
        if (failure === 'a non-OK reload') return Promise.resolve(jsonResponse({ error: 'reload failed' }, false));
        return Promise.resolve({ ok: true, status: 200, json: async () => { throw new Error('invalid JSON'); } } as unknown as Response);
      }) as unknown as typeof window.fetch;
      const dom = createReviewDom(page.file, fetch);

      try {
        const { document } = dom.window;
        await vi.waitFor(() => expect(document.getElementById('position')?.textContent).toBe('1 / 2'));
        const notes = document.querySelector<HTMLTextAreaElement>('textarea')!;
        const reason = document.querySelector<HTMLInputElement>('#rejection-reason');
        notes.value = 'draft survives reload failure';
        if (reason) reason.value = 'reason survives reload failure';
        saveButton(document, page).click();
        await vi.waitFor(() => expect(document.getElementById('status')?.textContent).toMatch(/save failed/i));
        expect(fetch).toHaveBeenCalledTimes(3);
        expect(document.getElementById('position')?.textContent).toBe('1 / 2');
        expect(notes.value).toBe('draft survives reload failure');
        expect(reason?.value ?? '').toBe(reason ? 'reason survives reload failure' : '');
        expect(savedBox(bodies[0], page)).toEqual(box);
        expect(document.querySelector('main')?.getAttribute('aria-busy')).toBe('false');
        saveButton(document, page).click();
        await vi.waitFor(() => expect(bodies).toHaveLength(2));
        expect(savedBox(bodies[1], page)).toEqual(box);
        await vi.waitFor(() => expect(fetch).toHaveBeenCalledTimes(5));
        await vi.waitFor(() => expect(document.querySelector('main')?.getAttribute('aria-busy')).toBe('false'));
      } finally {
        dom.window.close();
      }
    }
  });
});
