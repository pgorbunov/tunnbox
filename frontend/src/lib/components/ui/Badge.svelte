<script lang="ts">
	import type { Snippet } from 'svelte';

	export type BadgeTone = 'neutral' | 'success' | 'warning' | 'danger' | 'info' | 'accent';

	interface Props {
		tone?: BadgeTone;
		size?: 'sm' | 'md';
		outline?: boolean;
		class?: string;
		title?: string;
		children: Snippet;
	}

	let { tone = 'neutral', size = 'md', outline = false, class: className = '', title, children }: Props = $props();

	const TONES: Record<BadgeTone, string> = {
		neutral: 'bg-bg-subtle text-fg-muted border-border',
		success: 'bg-success-soft text-success border-transparent',
		warning: 'bg-warning-soft text-warning border-transparent',
		danger: 'bg-danger-soft text-danger border-transparent',
		info: 'bg-info-soft text-info border-transparent',
		accent: 'bg-accent-soft text-accent border-transparent'
	};
</script>

<span
	{title}
	class={`inline-flex items-center gap-1 whitespace-nowrap rounded-full border font-medium
		${size === 'sm' ? 'h-5 px-1.5 text-[11px]' : 'h-6 px-2 text-xs'}
		${outline ? 'bg-transparent' : ''} ${TONES[tone]} ${className}`}
>
	{@render children()}
</span>
