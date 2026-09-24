<script lang="ts">
	import type { Interface } from '$lib/api/types';
	import Badge from '$lib/components/ui/Badge.svelte';
	import StatusDot from './StatusDot.svelte';

	let { iface, size = 'md' }: { iface: Pick<Interface, 'enabled' | 'is_active'>; size?: 'sm' | 'md' } = $props();

	const state = $derived(
		iface.is_active
			? { tone: 'success' as const, label: 'Up', pulse: true }
			: iface.enabled
				? { tone: 'warning' as const, label: 'Enabled, not running', pulse: false }
				: { tone: 'neutral' as const, label: 'Down', pulse: false }
	);
</script>

<Badge tone={state.tone} {size}>
	<StatusDot tone={state.tone} pulse={state.pulse} size="sm" />
	{state.label}
</Badge>
