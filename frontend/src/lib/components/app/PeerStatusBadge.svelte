<script lang="ts">
	import type { PeerStatus } from '$lib/api/types';
	import Badge from '$lib/components/ui/Badge.svelte';
	import StatusDot from './StatusDot.svelte';

	let { status, size = 'md' }: { status: PeerStatus; size?: 'sm' | 'md' } = $props();

	const MAP = {
		online: { tone: 'success', label: 'Online', pulse: true },
		offline: { tone: 'neutral', label: 'Offline', pulse: false },
		disabled: { tone: 'warning', label: 'Disabled', pulse: false },
		expired: { tone: 'danger', label: 'Expired', pulse: false }
	} as const;
	const m = $derived(MAP[status]);
</script>

<Badge tone={m.tone} {size}>
	<StatusDot tone={m.tone} pulse={m.pulse} size="sm" />
	{m.label}
</Badge>
