/**
 * createPoller(fn, { intervalMs }) — runs `fn` immediately and then on an
 * interval; pauses while the tab is hidden, refreshes immediately when it
 * becomes visible or the window regains focus, and never overlaps calls.
 *
 * - `refresh()` aborts any in-flight request and starts a new one right away
 *   (so a filter/route change never waits for a stale tick).
 * - Every tick carries a generation number; results from an older generation
 *   are discarded, so data from a previous route can't land under a new URL.
 * - Backoff: 429 honours `Retry-After`; 5xx / network doubles the interval
 *   (capped at 60s) and resets on the next success.
 *
 * Use inside a component: `const poller = createPoller(load, { intervalMs })`,
 * then `$effect(() => poller.start())` — start returns the stop function.
 */
import { isAbortError, toApiError, type ApiError } from '$lib/api/client';

export interface PollerOptions {
	intervalMs: number | (() => number);
	/** Start immediately on `start()` (default true). */
	immediate?: boolean;
	/** Called with the ApiError when a tick fails. */
	onError?: (err: ApiError) => void;
}

export interface Poller {
	readonly refreshing: boolean;
	readonly loading: boolean;
	readonly lastUpdated: number | null;
	readonly error: ApiError | null;
	refresh(): Promise<void>;
	start(): () => void;
	stop(): void;
}

const MAX_BACKOFF_MS = 60_000;

export function createPoller(fn: (signal: AbortSignal) => Promise<void>, opts: PollerOptions): Poller {
	let refreshing = $state(false);
	let loading = $state(true);
	let lastUpdated = $state<number | null>(null);
	let error = $state<ApiError | null>(null);

	let timer: ReturnType<typeof setTimeout> | null = null;
	let controller: AbortController | null = null;
	let running = false;
	let inflight: Promise<void> | null = null;
	let generation = 0;
	let failures = 0;

	const interval = () => {
		const v = typeof opts.intervalMs === 'function' ? opts.intervalMs() : opts.intervalMs;
		return Number.isFinite(v) && v > 0 ? v : 10_000;
	};

	function delayFor(err: ApiError | null): number {
		const base = interval();
		if (!err) return base;
		if (err.status === 429 && err.retryAfter) return Math.max(base, err.retryAfter * 1000);
		if (err.status >= 500 || err.status === 0) return Math.min(MAX_BACKOFF_MS, base * 2 ** failures);
		return base;
	}

	function schedule(ms = interval()) {
		if (!running) return;
		if (timer) clearTimeout(timer);
		timer = setTimeout(() => void tick(), ms);
	}

	function cancelInflight() {
		controller?.abort();
		controller = null;
		inflight = null;
		generation += 1;
	}

	async function tick(): Promise<void> {
		if (inflight) return inflight;
		if (typeof document !== 'undefined' && document.hidden) {
			schedule();
			return;
		}
		const gen = ++generation;
		const ctl = new AbortController();
		controller = ctl;
		refreshing = true;
		inflight = (async () => {
			let delay = interval();
			try {
				await fn(ctl.signal);
				if (gen !== generation) return;
				error = null;
				failures = 0;
				lastUpdated = Date.now();
			} catch (err) {
				if (isAbortError(err) || gen !== generation) return;
				const e = toApiError(err);
				error = e;
				if (e.status >= 500 || e.status === 0) failures += 1;
				delay = delayFor(e);
				opts.onError?.(e);
			} finally {
				if (gen === generation) {
					refreshing = false;
					loading = false;
					inflight = null;
					controller = null;
					schedule(delay);
				}
			}
		})();
		return inflight;
	}

	function onVisible() {
		if (!document.hidden && running) void tick();
	}

	function stop() {
		running = false;
		if (timer) clearTimeout(timer);
		timer = null;
		cancelInflight();
		refreshing = false;
		if (typeof document !== 'undefined') {
			document.removeEventListener('visibilitychange', onVisible);
			window.removeEventListener('focus', onVisible);
		}
	}

	function start() {
		if (running) return stop;
		running = true;
		document.addEventListener('visibilitychange', onVisible);
		window.addEventListener('focus', onVisible);
		if (opts.immediate ?? true) void tick();
		else schedule();
		return stop;
	}

	/** Abort whatever is in flight and fetch again now. */
	function refresh(): Promise<void> {
		cancelInflight();
		if (timer) clearTimeout(timer);
		timer = null;
		return tick();
	}

	return {
		get refreshing() {
			return refreshing;
		},
		get loading() {
			return loading;
		},
		get lastUpdated() {
			return lastUpdated;
		},
		get error() {
			return error;
		},
		refresh,
		start,
		stop
	};
}

/** A `$state` clock ticking every `ms` — for "updated 5s ago" style labels. */
export function createTicker(ms = 1000): { readonly now: number } {
	let now = $state(Date.now());
	$effect(() => {
		const id = setInterval(() => (now = Date.now()), ms);
		return () => clearInterval(id);
	});
	return {
		get now() {
			return now;
		}
	};
}
