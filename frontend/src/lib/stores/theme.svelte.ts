/**
 * Theme: 'light' | 'dark' | 'system'. Persisted in localStorage (a per-viewer
 * preference, not a secret). `system` follows `prefers-color-scheme` live.
 */
import { browser } from '$app/environment';

export type Theme = 'light' | 'dark' | 'system';
const KEY = 'tb:theme';

function readStored(): Theme {
	if (!browser) return 'system';
	try {
		const v = localStorage.getItem(KEY);
		if (v === 'light' || v === 'dark' || v === 'system') return v;
	} catch {
		/* storage unavailable */
	}
	return 'system';
}

let theme = $state<Theme>(readStored());
let systemDark = $state<boolean>(browser ? window.matchMedia('(prefers-color-scheme: dark)').matches : false);
let initialized = false;

function apply(resolved: 'light' | 'dark') {
	if (!browser) return;
	const el = document.documentElement;
	el.classList.toggle('dark', resolved === 'dark');
	el.classList.toggle('light', resolved === 'light');
}

export const themeStore = {
	get theme() {
		return theme;
	},
	get resolved(): 'light' | 'dark' {
		return theme === 'system' ? (systemDark ? 'dark' : 'light') : theme;
	},
	set(next: Theme) {
		theme = next;
		try {
			localStorage.setItem(KEY, next);
		} catch {
			/* ignore */
		}
		apply(themeStore.resolved);
	},
	toggle() {
		themeStore.set(themeStore.resolved === 'dark' ? 'light' : 'dark');
	},
	/** Apply on mount and keep following the OS while in `system` mode. */
	init() {
		if (!browser || initialized) return;
		initialized = true;
		const mq = window.matchMedia('(prefers-color-scheme: dark)');
		systemDark = mq.matches;
		apply(themeStore.resolved);
		mq.addEventListener('change', (e) => {
			systemDark = e.matches;
			if (theme === 'system') apply(themeStore.resolved);
		});
	}
};
