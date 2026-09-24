export type ToastKind = 'success' | 'error' | 'info' | 'warning';

export interface ToastAction {
	label: string;
	onClick: () => void;
}

export interface Toast {
	id: number;
	kind: ToastKind;
	title: string;
	description?: string;
	action?: ToastAction;
	/** ms; 0 = sticky */
	duration: number;
}

let toasts = $state<Toast[]>([]);
let seq = 0;
const timers = new Map<number, ReturnType<typeof setTimeout>>();

function add(
	kind: ToastKind,
	title: string,
	opts: { description?: string; action?: ToastAction; duration?: number } = {}
) {
	const id = ++seq;
	const duration = opts.duration ?? (kind === 'error' ? 8000 : 4500);
	toasts = [...toasts, { id, kind, title, description: opts.description, action: opts.action, duration }];
	if (duration > 0)
		timers.set(
			id,
			setTimeout(() => dismiss(id), duration)
		);
	return id;
}

function dismiss(id: number) {
	const t = timers.get(id);
	if (t) clearTimeout(t);
	timers.delete(id);
	toasts = toasts.filter((t) => t.id !== id);
}

export const toast = {
	get items() {
		return toasts;
	},
	success: (title: string, opts?: { description?: string; action?: ToastAction; duration?: number }) =>
		add('success', title, opts),
	error: (title: string, opts?: { description?: string; action?: ToastAction; duration?: number }) =>
		add('error', title, opts),
	info: (title: string, opts?: { description?: string; action?: ToastAction; duration?: number }) =>
		add('info', title, opts),
	warning: (title: string, opts?: { description?: string; action?: ToastAction; duration?: number }) =>
		add('warning', title, opts),
	dismiss,
	/** Pause auto-dismiss (e.g. on hover). */
	pause(id: number) {
		const t = timers.get(id);
		if (t) {
			clearTimeout(t);
			timers.delete(id);
		}
	},
	resume(id: number) {
		const item = toasts.find((t) => t.id === id);
		if (item && item.duration > 0 && !timers.has(id)) {
			timers.set(
				id,
				setTimeout(() => dismiss(id), 2000)
			);
		}
	}
};
