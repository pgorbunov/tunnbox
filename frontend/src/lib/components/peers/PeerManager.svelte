<script lang="ts">
	/**
	 * Composes the peer table with its drawer, forms, onboarding modal, share
	 * dialog, confirmations and bulk bar. Pages own the data; this component
	 * owns the interactions and reports mutations back through callbacks.
	 */
	import type { Snippet } from 'svelte';
	import { SvelteSet } from 'svelte/reactivity';
	import { api, toApiError } from '$lib/api';
	import type { BulkAction, Interface, Peer } from '$lib/api/types';
	import { auth } from '$lib/stores/auth.svelte';
	import { toast } from '$lib/stores/toast.svelte';
	import ConfirmDialog from '$lib/components/ui/ConfirmDialog.svelte';
	import type { PeerAction } from './actions';
	import BulkActionBar from './BulkActionBar.svelte';
	import PeerDrawer from './PeerDrawer.svelte';
	import PeerForm from './PeerForm.svelte';
	import PeerOnboardModal, { type OnboardTab } from './PeerOnboardModal.svelte';
	import PeerTable from './PeerTable.svelte';
	import ShareLinkModal from './ShareLinkModal.svelte';

	interface Props {
		peers: Peer[];
		interfaces: Interface[];
		loading?: boolean;
		refreshing?: boolean;
		/** Interface used for "New peer"; when omitted, creation is not offered here. */
		iface?: Interface | null;
		createOpen?: boolean;
		/** Peer id to open in the drawer (e.g. from ?peer=). */
		focusPeerId?: number | null;
		showInterface?: boolean;
		sortKey?: string;
		sortOrder?: 'asc' | 'desc';
		onsort?: (key: string, order: 'asc' | 'desc') => void;
		empty?: Snippet;
		onupdated: (peer: Peer) => void;
		oncreated: (peer: Peer) => void;
		ondeleted: (ids: number[]) => void;
		onrefresh: () => void;
	}

	let {
		peers,
		interfaces,
		loading = false,
		refreshing = false,
		iface = null,
		createOpen = $bindable(false),
		focusPeerId = $bindable(null),
		showInterface = false,
		sortKey,
		sortOrder,
		onsort,
		empty,
		onupdated,
		oncreated,
		ondeleted,
		onrefresh
	}: Props = $props();

	const canWrite = $derived(auth.can('operator'));
	const selected = new SvelteSet<number>();

	let drawerOpen = $state(false);
	let drawerPeer = $state<Peer | null>(null);
	let editOpen = $state(false);
	let editPeer = $state<Peer | null>(null);
	let onboardOpen = $state(false);
	let onboardPeer = $state<Peer | null>(null);
	let onboardTab = $state<OnboardTab>('qr');
	let onboardJustCreated = $state(false);
	let shareOpen = $state(false);
	let sharePeer = $state<Peer | null>(null);
	let deleteOpen = $state(false);
	let deletePeer = $state<Peer | null>(null);
	let deleting = $state(false);
	let rotateOpen = $state(false);
	let rotatePeer = $state<Peer | null>(null);
	let rotating = $state(false);
	let bulkLoading = $state<BulkAction | null>(null);
	let bulkDeleteOpen = $state(false);

	function ifaceFor(peer: Peer | null): Interface | null {
		if (!peer) return iface;
		return interfaces.find((i) => i.id === peer.interface_id || i.name === peer.interface_name) ?? iface;
	}

	// Keep the drawer's peer fresh as the list refreshes.
	$effect(() => {
		if (drawerPeer) {
			const fresh = peers.find((p) => p.id === drawerPeer!.id);
			if (fresh && fresh !== drawerPeer) drawerPeer = fresh;
		}
	});

	$effect(() => {
		if (focusPeerId !== null && peers.length) {
			const p = peers.find((x) => x.id === focusPeerId);
			if (p) {
				drawerPeer = p;
				drawerOpen = true;
			}
			focusPeerId = null;
		}
	});

	// Drop selections for peers that disappeared.
	$effect(() => {
		const ids = new Set(peers.map((p) => p.id));
		for (const id of selected) if (!ids.has(id)) selected.delete(id);
	});

	function openDrawer(peer: Peer) {
		drawerPeer = peer;
		drawerOpen = true;
	}

	async function toggle(peer: Peer) {
		try {
			const updated = peer.enabled ? await api.peers.disable(peer.id) : await api.peers.enable(peer.id);
			onupdated(updated);
			toast.success(`${updated.name} ${updated.enabled ? 'enabled' : 'disabled'}`);
		} catch (err) {
			toast.error(`Could not ${peer.enabled ? 'disable' : 'enable'} ${peer.name}`, { description: toApiError(err).detail });
		}
	}

	function handleAction(action: PeerAction, peer: Peer) {
		switch (action) {
			case 'details':
				openDrawer(peer);
				break;
			case 'qr':
			case 'download':
				onboardPeer = peer;
				onboardTab = action;
				onboardJustCreated = false;
				onboardOpen = true;
				break;
			case 'share':
				sharePeer = peer;
				shareOpen = true;
				break;
			case 'edit':
				editPeer = peer;
				editOpen = true;
				break;
			case 'toggle':
				void toggle(peer);
				break;
			case 'rotate':
				rotatePeer = peer;
				rotateOpen = true;
				break;
			case 'delete':
				deletePeer = peer;
				deleteOpen = true;
				break;
		}
	}

	async function confirmDelete() {
		if (!deletePeer) return;
		deleting = true;
		try {
			await api.peers.remove(deletePeer.id);
			toast.success(`Deleted ${deletePeer.name}`);
			ondeleted([deletePeer.id]);
			if (drawerPeer?.id === deletePeer.id) drawerOpen = false;
			deleteOpen = false;
		} catch (err) {
			toast.error('Could not delete peer', { description: toApiError(err).detail });
		} finally {
			deleting = false;
		}
	}

	async function confirmRotate() {
		if (!rotatePeer) return;
		rotating = true;
		try {
			const updated = await api.peers.rotateKeys(rotatePeer.id);
			onupdated(updated);
			rotateOpen = false;
			toast.success(`Keys rotated for ${updated.name}`, { description: 'The previous client configuration no longer works.' });
			onboardPeer = updated;
			onboardTab = 'qr';
			onboardJustCreated = false;
			onboardOpen = true;
		} catch (err) {
			toast.error('Could not rotate keys', { description: toApiError(err).detail });
		} finally {
			rotating = false;
		}
	}

	async function runBulk(action: BulkAction) {
		if (action === 'delete' && !bulkDeleteOpen) {
			bulkDeleteOpen = true;
			return;
		}
		const ids = [...selected];
		bulkLoading = action;
		try {
			const res = await api.peers.bulk({ ids, action });
			toast.success(`${res.affected} ${res.affected === 1 ? 'peer' : 'peers'} ${action === 'delete' ? 'deleted' : `${action}d`}`);
			if (action === 'delete') ondeleted(ids);
			selected.clear();
			bulkDeleteOpen = false;
			onrefresh();
		} catch (err) {
			toast.error(`Bulk ${action} failed`, { description: toApiError(err).detail });
		} finally {
			bulkLoading = null;
		}
	}

	function handleSaved(peer: Peer, created: boolean) {
		if (created) {
			oncreated(peer);
			onboardPeer = peer;
			onboardTab = 'qr';
			onboardJustCreated = true;
			onboardOpen = true;
		} else {
			onupdated(peer);
		}
	}

	const editIface = $derived(ifaceFor(editPeer));
</script>

<PeerTable
	{peers}
	{loading}
	{refreshing}
	{sortKey}
	{sortOrder}
	{onsort}
	{selected}
	{canWrite}
	{showInterface}
	onopen={openDrawer}
	onaction={handleAction}
	{empty}
/>

{#if canWrite}
	<BulkActionBar count={selected.size} loading={bulkLoading} onaction={(a) => void runBulk(a)} onclear={() => selected.clear()} />
{/if}

<PeerDrawer bind:open={drawerOpen} peer={drawerPeer} {canWrite} onaction={handleAction} />

{#if iface}
	<PeerForm bind:open={createOpen} {iface} onsaved={handleSaved} />
{/if}
{#if editIface}
	<PeerForm bind:open={editOpen} iface={editIface} peer={editPeer} onsaved={handleSaved} />
{/if}

<PeerOnboardModal
	bind:open={onboardOpen}
	peer={onboardPeer}
	ifaceAddress={ifaceFor(onboardPeer)?.address ?? ''}
	initialTab={onboardTab}
	justCreated={onboardJustCreated}
/>

<ShareLinkModal bind:open={shareOpen} peer={sharePeer} />

<ConfirmDialog
	bind:open={deleteOpen}
	title={`Delete ${deletePeer?.name ?? 'peer'}?`}
	message="The peer is removed from the interface and its client configuration stops working. This cannot be undone."
	confirmLabel="Delete peer"
	loading={deleting}
	onconfirm={confirmDelete}
/>

<ConfirmDialog
	bind:open={rotateOpen}
	title={`Rotate keys for ${rotatePeer?.name ?? 'peer'}?`}
	message="A new key pair and preshared key are generated. The device must be reconfigured with the new QR code or file."
	confirmLabel="Rotate keys"
	tone="primary"
	loading={rotating}
	onconfirm={confirmRotate}
/>

<ConfirmDialog
	bind:open={bulkDeleteOpen}
	title={`Delete ${selected.size} ${selected.size === 1 ? 'peer' : 'peers'}?`}
	message="The selected peers are removed permanently and their client configurations stop working."
	confirmLabel="Delete peers"
	loading={bulkLoading === 'delete'}
	onconfirm={() => runBulk('delete')}
/>
