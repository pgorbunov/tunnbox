/**
 * Global hotkeys: Ctrl/Cmd+K (command palette), ? (help), g d / g i / g p / g a / g s
 * (navigation chords), / (focus search on list pages).
 */
import { goto } from '$app/navigation';

export interface HotkeyHandlers {
	openPalette: () => void;
	openHelp: () => void;
}

export const NAV_CHORDS: Record<string, { path: string; label: string }> = {
	d: { path: '/', label: 'Dashboard' },
	i: { path: '/interfaces', label: 'Interfaces' },
	p: { path: '/peers', label: 'Peers' },
	a: { path: '/audit', label: 'Audit log' },
	s: { path: '/settings', label: 'Settings' }
};

export const HOTKEY_HELP: { keys: string[]; description: string }[] = [
	{ keys: ['Ctrl', 'K'], description: 'Open command palette' },
	{ keys: ['/'], description: 'Focus search on list pages' },
	{ keys: ['?'], description: 'Show keyboard shortcuts' },
	{ keys: ['g', 'd'], description: 'Go to dashboard' },
	{ keys: ['g', 'i'], description: 'Go to interfaces' },
	{ keys: ['g', 'p'], description: 'Go to peers' },
	{ keys: ['g', 'a'], description: 'Go to audit log' },
	{ keys: ['g', 's'], description: 'Go to settings' },
	{ keys: ['Esc'], description: 'Close dialogs and menus' }
];

export function isEditableTarget(target: EventTarget | null): boolean {
	if (!(target instanceof HTMLElement)) return false;
	if (target.isContentEditable) return true;
	const tag = target.tagName;
	return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';
}

/** Register global hotkeys; returns the cleanup function. */
export function registerHotkeys(handlers: HotkeyHandlers): () => void {
	let pendingG = 0;

	function onKeydown(e: KeyboardEvent) {
		const mod = e.metaKey || e.ctrlKey;
		if (mod && e.key.toLowerCase() === 'k') {
			e.preventDefault();
			handlers.openPalette();
			return;
		}
		if (mod || e.altKey) return;
		if (isEditableTarget(e.target)) return;
		// Overlays open? Let them handle keys.
		if (document.querySelector('dialog[open]')) return;

		if (e.key === '?') {
			e.preventDefault();
			handlers.openHelp();
			return;
		}
		if (e.key === '/') {
			const search = document.querySelector<HTMLInputElement>('[data-hotkey-search]');
			if (search) {
				e.preventDefault();
				search.focus();
				search.select();
			}
			return;
		}
		const now = Date.now();
		if (e.key === 'g') {
			pendingG = now;
			return;
		}
		if (pendingG && now - pendingG < 1200) {
			const chord = NAV_CHORDS[e.key];
			pendingG = 0;
			if (chord) {
				e.preventDefault();
				void goto(chord.path);
			}
		}
	}

	window.addEventListener('keydown', onKeydown);
	return () => window.removeEventListener('keydown', onKeydown);
}
