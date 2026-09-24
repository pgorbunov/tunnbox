<script lang="ts">
	import { ArrowDown, ArrowUp, Users } from 'lucide-svelte';
	import type { Interface } from '$lib/api/types';
	import { formatBytes } from '$lib/utils/format';
	import InterfaceStatusBadge from '$lib/components/app/InterfaceStatusBadge.svelte';
	import Switch from '$lib/components/ui/Switch.svelte';

	interface Props {
		iface: Interface;
		canWrite: boolean;
		toggling?: boolean;
		ontoggle: (iface: Interface, up: boolean) => void;
	}

	let { iface, canWrite, toggling = false, ontoggle }: Props = $props();
	const href = $derived(`/interfaces/${encodeURIComponent(iface.name)}`);
</script>

<article class="group relative flex flex-col gap-4 rounded-lg border border-border bg-surface p-4 shadow-sm transition-colors hover:border-border-strong">
	<div class="flex items-start justify-between gap-3">
		<div class="min-w-0">
			<h3 class="truncate font-mono text-base font-semibold text-fg">
				<a {href} class="after:absolute after:inset-0 after:content-[''] focus-visible:outline-none">{iface.name}</a>
			</h3>
			<p class="mt-0.5 truncate font-mono text-[12px] text-fg-muted">{iface.address} · :{iface.listen_port}</p>
		</div>
		<div class="relative z-10 flex items-center gap-3">
			<InterfaceStatusBadge {iface} size="sm" />
			{#if canWrite}
				<Switch
					checked={iface.enabled}
					label={`${iface.enabled ? 'Bring down' : 'Bring up'} ${iface.name}`}
					hideLabel
					size="sm"
					loading={toggling}
					onchange={(v) => ontoggle(iface, v)}
				/>
			{/if}
		</div>
	</div>
	<dl class="grid grid-cols-3 gap-2 text-[13px]">
		<div class="rounded-md bg-bg-subtle px-2.5 py-2">
			<dt class="flex items-center gap-1 text-[11px] font-medium uppercase tracking-wide text-fg-subtle"><Users class="h-3 w-3" aria-hidden="true" />Peers</dt>
			<dd class="tabular mt-0.5 font-semibold text-fg">
				{iface.online_peer_count}<span class="font-normal text-fg-subtle"> / {iface.peer_count}</span>
			</dd>
		</div>
		<div class="rounded-md bg-bg-subtle px-2.5 py-2">
			<dt class="flex items-center gap-1 text-[11px] font-medium uppercase tracking-wide text-fg-subtle"><ArrowDown class="h-3 w-3 text-chart-download" aria-hidden="true" />Down</dt>
			<dd class="tabular mt-0.5 font-semibold text-fg">{formatBytes(iface.rx_total)}</dd>
		</div>
		<div class="rounded-md bg-bg-subtle px-2.5 py-2">
			<dt class="flex items-center gap-1 text-[11px] font-medium uppercase tracking-wide text-fg-subtle"><ArrowUp class="h-3 w-3 text-chart-upload" aria-hidden="true" />Up</dt>
			<dd class="tabular mt-0.5 font-semibold text-fg">{formatBytes(iface.tx_total)}</dd>
		</div>
	</dl>
</article>
