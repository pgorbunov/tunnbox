import { writable } from 'svelte/store';
import { browser } from '$app/environment';

export type Theme = 'light' | 'dark' | 'auto';

function getSystemTheme(): 'light' | 'dark' {
	if (!browser) return 'dark';
	return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function getStoredTheme(): Theme {
	if (!browser) return 'dark';
	const stored = localStorage.getItem('theme');
	if (stored === 'light' || stored === 'dark' || stored === 'auto') {
		return stored;
	}
	return 'auto';
}

function createThemeStore() {
	const { subscribe, set, update } = writable<Theme>(getStoredTheme());

	return {
		subscribe,
		set: (theme: Theme) => {
			if (browser) {
				localStorage.setItem('theme', theme);
			}
			set(theme);
			applyTheme(theme);
		},
		initialize: () => {
			const theme = getStoredTheme();
			set(theme);
			applyTheme(theme);

			// Listen for system theme changes when in auto mode
			if (browser) {
				const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
				mediaQuery.addEventListener('change', () => {
					const currentTheme = getStoredTheme();
					if (currentTheme === 'auto') {
						applyTheme('auto');
					}
				});
			}
		}
	};
}

function applyTheme(theme: Theme) {
	if (!browser) return;

	const resolvedTheme = theme === 'auto' ? getSystemTheme() : theme;

	if (resolvedTheme === 'dark') {
		document.documentElement.classList.add('dark');
		document.documentElement.classList.remove('light');
	} else {
		document.documentElement.classList.add('light');
		document.documentElement.classList.remove('dark');
	}
}

export const theme = createThemeStore();
