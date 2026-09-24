<script lang="ts">
	import {
		Download,
		KeyRound,
		Link2,
		MoreHorizontal,
		Pencil,
		Power,
		PowerOff,
		QrCode,
		Trash2
	} from 'lucide-svelte';
	import type { Peer } from '$lib/api/types';
	import DropdownMenu, { type MenuItem } from '$lib/components/ui/DropdownMenu.svelte';
	import IconButton from '$lib/components/ui/IconButton.svelte';
	import type { PeerActionHandler } from './actions';

	interface Props {
		peer: Peer;
		canWrite: boolean;
		onaction: PeerActionHandler;
		size?: 'sm' | 'md';
	}

	let { peer, canWrite, onaction, size = 'sm' }: Props = $props();

	const items = $derived<MenuItem[]>([
		{
			label: 'Show QR code',
			icon: QrCode,
			onselect: () => onaction('qr', peer),
			disabled: !peer.has_private_key
		},
		{
			label: 'Download config',
			icon: Download,
			onselect: () => onaction('download', peer),
			disabled: !peer.has_private_key
		},
		{ label: 'Share link', icon: Link2, onselect: () => onaction('share', peer), hidden: !canWrite },
		{
			label: 'Edit',
			icon: Pencil,
			onselect: () => onaction('edit', peer),
			separator: true,
			hidden: !canWrite
		},
		{
			label: peer.enabled ? 'Disable' : 'Enable',
			icon: peer.enabled ? PowerOff : Power,
			onselect: () => onaction('toggle', peer),
			hidden: !canWrite
		},
		{ label: 'Rotate keys', icon: KeyRound, onselect: () => onaction('rotate', peer), hidden: !canWrite },
		{
			label: 'Delete',
			icon: Trash2,
			danger: true,
			separator: true,
			onselect: () => onaction('delete', peer),
			hidden: !canWrite
		}
	]);
</script>

<DropdownMenu {items} label={`Actions for ${peer.name}`}>
	{#snippet trigger({ toggle, props })}
		<IconButton label={`Actions for ${peer.name}`} {size} onclick={toggle} {...props}>
			<MoreHorizontal class="h-4 w-4" />
		</IconButton>
	{/snippet}
</DropdownMenu>
