/** Small DOM helpers and Svelte actions. */
import type { Action } from 'svelte/action';

let counter = 0;
/** Stable unique id for aria wiring. */
export function uid(prefix = 'tb'): string {
	counter += 1;
	return `${prefix}-${counter}`;
}

/** Calls `handler` when a pointerdown happens outside the node. */
export const clickOutside: Action<HTMLElement, (e: PointerEvent) => void> = (node, handler) => {
	let current = handler;
	function onPointerDown(e: PointerEvent) {
		if (!node.contains(e.target as Node)) current(e);
	}
	document.addEventListener('pointerdown', onPointerDown, true);
	return {
		update(next) {
			current = next;
		},
		destroy() {
			document.removeEventListener('pointerdown', onPointerDown, true);
		}
	};
};

/** Copies text to the clipboard; resolves false if not permitted. */
export async function copyText(text: string): Promise<boolean> {
	try {
		await navigator.clipboard.writeText(text);
		return true;
	} catch {
		try {
			const ta = document.createElement('textarea');
			ta.value = text;
			ta.setAttribute('readonly', '');
			ta.style.position = 'fixed';
			ta.style.opacity = '0';
			document.body.appendChild(ta);
			ta.select();
			const ok = document.execCommand('copy');
			ta.remove();
			return ok;
		} catch {
			return false;
		}
	}
}

export function prefersReducedMotion(): boolean {
	return typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/** Focus the first focusable element inside `root`, or `root` itself. */
export function focusFirst(root: HTMLElement): void {
	const el = root.querySelector<HTMLElement>(
		'[autofocus], input:not([type=hidden]):not([disabled]), textarea:not([disabled]), select:not([disabled]), button:not([disabled]), [href], [tabindex]:not([tabindex="-1"])'
	);
	(el ?? root).focus();
}

/** Focus the page's main heading after navigation (screen-reader friendly). */
export function focusMainHeading(): void {
	const h = document.querySelector<HTMLElement>('main h1, [data-page-heading]');
	if (h) {
		if (!h.hasAttribute('tabindex')) h.setAttribute('tabindex', '-1');
		h.focus({ preventScroll: true });
	}
}

/** Class-name joiner that drops falsy values. */
export function cn(...parts: Array<string | false | null | undefined>): string {
	return parts.filter(Boolean).join(' ');
}
