<script lang="ts">
	/** Active sessions with "This device" badge, per-session revoke and "Sign out everywhere else". */
	import { LogOut, Monitor, Smartphone } from 'lucide-svelte';
	import { api, toApiError } from '$lib/api';
	import type { Session } from '$lib/api/types';
	import { toast } from '$lib/stores/toast.svelte';
	import { formatDateTime, formatRelative } from '$lib/utils/format';
	import Badge from '$lib/components/ui/Badge.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import ConfirmDialog from '$lib/components/ui/ConfirmDialog.svelte';
	import ErrorState from '$lib/components/ui/ErrorState.svelte';
	import Skeleton from '$lib/components/ui/Skeleton.svelte';

	let sessions = $state<Session[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let revoking = $state<string | null>(null);
	let revokeAllOpen = $state(false);
	let revokingAll = $state(false);

	async function load() {
		loading = true;
		error = null;
		try {
			sessions = await api.auth.sessions();
		} catch (err) {
			error = toApiError(err).detail;
		} finally {
			loading = false;
		}
	}
	$effect(() => {
		void load();
	});

	function describe(ua: string | null): { label: string; mobile: boolean } {
		if (!ua) return { label: 'Unknown device', mobile: false };
		const mobile = /Mobile|Android|iPhone|iPad/i.test(ua);
		const browser = /Firefox\/(\d+)/.exec(ua)?.[0] ?? /Edg\/(\d+)/.exec(ua)?.[0].replace('Edg', 'Edge') ?? /Chrome\/(\d+)/.exec(ua)?.[0] ?? (/Safari/.test(ua) ? 'Safari' : ua.slice(0, 40));
		const os = /Windows/.test(ua) ? 'Windows' : /Mac OS X/.test(ua) ? 'macOS' : /Android/.test(ua) ? 'Android' : /iPhone|iPad/.test(ua) ? 'iOS' : /Linux/.test(ua) ? 'Linux' : '';
		return { label: [browser.replace('/', ' '), os].filter(Boolean).join(' · '), mobile };
	}

	async function revoke(s: Session) {
		revoking = s.id;
		try {
			await api.auth.revokeSession(s.id);
			sessions = sessions.filter((x) => x.id !== s.id);
			toast.success('Session revoked');
		} catch (err) {
			toast.error('Could not revoke session', { description: toApiError(err).detail });
		} finally {
			revoking = null;
		}
	}

	async function revokeAll() {
		revokingAll = true;
		try {
			await api.auth.revokeOtherSessions();
			sessions = sessions.filter((x) => x.current);
			revokeAllOpen = false;
			toast.success('Signed out everywhere else');
		} catch (err) {
			toast.error('Could not revoke sessions', { description: toApiError(err).detail });
		} finally {
			revokingAll = false;
		}
	}

	const others = $derived(sessions.filter((s) => !s.current).length);
</script>

<Card title="Sessions" description="Devices currently signed in to your account." flush>
	{#snippet actions()}
		<Button size="sm" variant="danger-soft" disabled={others === 0} onclick={() => (revokeAllOpen = true)}>
			<LogOut class="h-4 w-4" aria-hidden="true" />
			Sign out everywhere else
		</Button>
	{/snippet}

	{#if loading}
		<div class="divide-y divide-border">
			{#each [1, 2] as i (i)}
				<div class="flex items-center gap-4 px-5 py-4"><Skeleton class="h-9 w-9" rounded="md" /><div class="flex-1"><Skeleton class="h-4 w-48" /><Skeleton class="mt-2 h-3 w-32" /></div></div>
			{/each}
		</div>
	{:else if error}
		<ErrorState compact message={error} onretry={load} />
	{:else}
		<ul class="divide-y divide-border">
			{#each sessions as s (s.id)}
				{@const d = describe(s.user_agent)}
				<li class="flex items-center gap-4 px-5 py-4">
					<span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-bg-subtle text-fg-subtle" aria-hidden="true">
						{#if d.mobile}<Smartphone class="h-5 w-5" />{:else}<Monitor class="h-5 w-5" />{/if}
					</span>
					<div class="min-w-0 flex-1 text-sm">
						<p class="flex flex-wrap items-center gap-2 font-medium text-fg">
							<span class="truncate">{d.label}</span>
							{#if s.current}<Badge tone="accent" size="sm">This device</Badge>{/if}
						</p>
						<p class="mt-0.5 text-[13px] text-fg-subtle">
							{s.ip ?? 'Unknown IP'} · Last active {formatRelative(s.last_used_at)} · Signed in {formatDateTime(s.created_at)}
						</p>
					</div>
					{#if !s.current}
						<Button size="sm" variant="ghost" onclick={() => revoke(s)} loading={revoking === s.id}>Revoke</Button>
					{/if}
				</li>
			{/each}
		</ul>
	{/if}
</Card>

<ConfirmDialog
	bind:open={revokeAllOpen}
	title="Sign out everywhere else?"
	message={`${others} other ${others === 1 ? 'session' : 'sessions'} will be signed out immediately. This device stays signed in.`}
	confirmLabel="Sign out others"
	loading={revokingAll}
	onconfirm={revokeAll}
/>
