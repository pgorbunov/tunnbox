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
const DEFAULT_PREFS: UiPrefs = { sidebarCollapsed: false, density: 'comfortable', refreshSeconds: null };

function readPrefs(): UiPrefs {
	if (!browser) return { ...DEFAULT_PREFS };
	try {
		const raw = localStorage.getItem(PREFS_KEY);
		if (!raw) return { ...DEFAULT_PREFS };
		const parsed = JSON.parse(raw) as Partial<UiPrefs>;
		return { ...DEFAULT_PREFS, ...parsed };
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
		const s = prefs.refreshSeconds ?? server?.ui_refresh_seconds ?? 10;
		return Math.max(3, s) * 1000;
	},
	setPrefs(patch: Partial<UiPrefs>) {
		prefs = { ...prefs, ...patch };
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
