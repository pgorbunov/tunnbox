<script lang="ts">
	export type DotTone = 'success' | 'neutral' | 'warning' | 'danger' | 'info';
	interface Props {
		tone: DotTone;
		pulse?: boolean;
		size?: 'sm' | 'md';
		class?: string;
	}
	let { tone, pulse = false, size = 'md', class: className = '' }: Props = $props();
	const TONES: Record<DotTone, string> = {
		success: 'bg-success',
		neutral: 'bg-fg-subtle/60',
		warning: 'bg-warning',
		danger: 'bg-danger',
		info: 'bg-info'
	};
</script>

<span
	class={`inline-block shrink-0 rounded-full ${size === 'sm' ? 'h-2 w-2' : 'h-2.5 w-2.5'} ${TONES[tone]} ${pulse ? 'status-pulse' : ''} ${className}`}
	aria-hidden="true"
></span>
