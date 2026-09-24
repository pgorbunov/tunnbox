/**
 * createPoller(fn, { intervalMs }) — runs `fn` immediately and then on an
 * interval; pauses while the tab is hidden, refreshes immediately when it
 * becomes visible or the window regains focus, and never overlaps calls.
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

export function createPoller(fn: (signal: AbortSignal) => Promise<void>, opts: PollerOptions): Poller {
	let refreshing = $state(false);
	let loading = $state(true);
	let lastUpdated = $state<number | null>(null);
	let error = $state<ApiError | null>(null);

	let timer: ReturnType<typeof setTimeout> | null = null;
	let controller: AbortController | null = null;
	let running = false;
	let inflight: Promise<void> | null = null;

	const interval = () => (typeof opts.intervalMs === 'function' ? opts.intervalMs() : opts.intervalMs);

	function schedule() {
		if (!running) return;
		if (timer) clearTimeout(timer);
		timer = setTimeout(() => void tick(), interval());
	}

	async function tick(): Promise<void> {
		if (inflight) return inflight;
		if (typeof document !== 'undefined' && document.hidden) {
			schedule();
			return;
		}
		controller = new AbortController();
		refreshing = true;
		inflight = (async () => {
			try {
				await fn(controller!.signal);
				error = null;
				lastUpdated = Date.now();
			} catch (err) {
				if (isAbortError(err)) return;
				const e = toApiError(err);
				error = e;
				opts.onError?.(e);
			} finally {
				refreshing = false;
				loading = false;
				inflight = null;
				schedule();
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
		controller?.abort();
		controller = null;
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
		refresh: () => tick(),
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
