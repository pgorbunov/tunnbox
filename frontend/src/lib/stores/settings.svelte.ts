/**
 * Server settings cache (fetched once per session, refreshed on demand) plus
 * per-viewer UI preferences persisted in localStorage.
 */
import { browser } from '$app/environment';
import { api } from '$lib/api';
import type { Settings } from '$lib/api/types';

export type Density = 'comfortable' | 'compact';

export interface UiPrefs {
	sidebarCollapsed: boolean;
	density: Density;
	/** Overrides the server `ui_refresh_seconds` when set. */
	refreshSeconds: number | null;
}

const PREFS_KEY = 'tb:ui';
const MIN_REFRESH_S = 3;
const MAX_REFRESH_S = 300;

/** A finite number of seconds within [3, 300], or null (use the server value). */
function clampSeconds(v: unknown): number | null {
	if (typeof v !== 'number' || !Number.isFinite(v)) return null;
	return Math.min(MAX_REFRESH_S, Math.max(MIN_REFRESH_S, Math.round(v)));
}
const DEFAULT_PREFS: UiPrefs = { sidebarCollapsed: false, density: 'comfortable', refreshSeconds: null };

function readPrefs(): UiPrefs {
	if (!browser) return { ...DEFAULT_PREFS };
	try {
		const raw = localStorage.getItem(PREFS_KEY);
		if (!raw) return { ...DEFAULT_PREFS };
		const parsed = JSON.parse(raw) as Partial<Record<keyof UiPrefs, unknown>>;
		return {
			sidebarCollapsed: parsed.sidebarCollapsed === true,
			density: parsed.density === 'compact' ? 'compact' : 'comfortable',
			refreshSeconds: clampSeconds(parsed.refreshSeconds)
		};
	} catch {
		return { ...DEFAULT_PREFS };
	}
}

let prefs = $state<UiPrefs>(readPrefs());
let server = $state<Settings | null>(null);
let loading = $state(false);
let inflight: Promise<Settings> | null = null;

function persist() {
	try {
		localStorage.setItem(PREFS_KEY, JSON.stringify(prefs));
	} catch {
		/* ignore */
	}
}

export const settingsStore = {
	get prefs() {
		return prefs;
	},
	get server() {
		return server;
	},
	get loading() {
		return loading;
	},
	/** Effective polling interval in ms (prefers user override, then server, then 10s). */
	get refreshMs(): number {
		const s = clampSeconds(prefs.refreshSeconds) ?? clampSeconds(server?.ui_refresh_seconds) ?? 10;
		return s * 1000;
	},
	setPrefs(patch: Partial<UiPrefs>) {
		const next = { ...prefs, ...patch };
		if ('refreshSeconds' in patch) next.refreshSeconds = clampSeconds(patch.refreshSeconds);
		prefs = next;
		persist();
	},
	toggleSidebar() {
		settingsStore.setPrefs({ sidebarCollapsed: !prefs.sidebarCollapsed });
	},
	/** Load server settings (deduplicated). */
	async load(force = false): Promise<Settings> {
		if (server && !force) return server;
		if (inflight) return inflight;
		loading = true;
		inflight = api.settings
			.get()
			.then((s) => {
				server = s;
				return s;
			})
			.finally(() => {
				loading = false;
				inflight = null;
			});
		return inflight;
	},
	set(s: Settings) {
		server = s;
	},
	reset() {
		server = null;
	}
};
