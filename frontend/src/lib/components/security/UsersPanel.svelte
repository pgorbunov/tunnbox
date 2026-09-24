<script lang="ts">
	/** Admin user management: table, create/edit dialog, deactivate, reset password / MFA, delete. */
	import { MoreHorizontal, Plus, Users } from 'lucide-svelte';
	import { api, toApiError } from '$lib/api';
	import type { Role, User } from '$lib/api/types';
	import { auth } from '$lib/stores/auth.svelte';
	import { toast } from '$lib/stores/toast.svelte';
	import { formatDateTime, formatRelative } from '$lib/utils/format';
	import { validatePassword, validateUsername } from '$lib/utils/validation';
	import Alert from '$lib/components/ui/Alert.svelte';
	import Badge from '$lib/components/ui/Badge.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import ConfirmDialog from '$lib/components/ui/ConfirmDialog.svelte';
	import Dialog from '$lib/components/ui/Dialog.svelte';
	import DropdownMenu, { type MenuItem } from '$lib/components/ui/DropdownMenu.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import ErrorState from '$lib/components/ui/ErrorState.svelte';
	import IconButton from '$lib/components/ui/IconButton.svelte';
	import Input from '$lib/components/ui/Input.svelte';
	import Select from '$lib/components/ui/Select.svelte';
	import Table, { type Column } from '$lib/components/ui/Table.svelte';

	const ROLES: { value: Role; label: string }[] = [
		{ value: 'admin', label: 'Admin' },
		{ value: 'operator', label: 'Operator' },
		{ value: 'viewer', label: 'Viewer' }
	];

	let users = $state<User[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);

	type Mode = 'create' | 'edit' | 'password';
	let dialogOpen = $state(false);
	let mode = $state<Mode>('create');
	let target = $state<User | null>(null);
	let username = $state('');
	let password = $state('');
	let role = $state<Role>('operator');
	let saving = $state(false);
	let formError = $state<string | null>(null);
	let touched = $state(false);

	let confirmOpen = $state(false);
	let confirmKind = $state<'delete' | 'deactivate' | 'activate' | 'resetMfa'>('delete');
	let confirmTarget = $state<User | null>(null);
	let confirming = $state(false);

	const me = $derived(auth.user);

	async function load() {
		loading = true;
		error = null;
		try {
			users = await api.users.list();
		} catch (err) {
			error = toApiError(err).detail;
		} finally {
			loading = false;
		}
	}
	$effect(() => {
		void load();
	});

	function openDialog(m: Mode, u: User | null = null) {
		mode = m;
		target = u;
		username = u?.username ?? '';
		password = '';
		role = u?.role ?? 'operator';
		formError = null;
		touched = false;
		dialogOpen = true;
	}

	const errors = $derived({
		username: mode === 'create' ? validateUsername(username) : null,
		password: mode !== 'edit' ? validatePassword(password, username) : null
	});
	const valid = $derived(!errors.username && !errors.password);

	async function save() {
		touched = true;
		if (!valid || saving) return;
		saving = true;
		formError = null;
		try {
			if (mode === 'create') {
				const u = await api.users.create({ username: username.trim(), password, role });
				users = [...users, u];
				toast.success(`User ${u.username} created`);
			} else if (mode === 'edit' && target) {
				const u = await api.users.update(target.id, { role });
				users = users.map((x) => (x.id === u.id ? u : x));
				toast.success(`Role updated for ${u.username}`);
			} else if (mode === 'password' && target) {
				const u = await api.users.update(target.id, { password });
				users = users.map((x) => (x.id === u.id ? u : x));
				toast.success(`Password reset for ${u.username}`);
			}
			dialogOpen = false;
		} catch (err) {
			formError = toApiError(err).detail;
		} finally {
			saving = false;
		}
	}

	function ask(kind: typeof confirmKind, u: User) {
		confirmKind = kind;
		confirmTarget = u;
		confirmOpen = true;
	}

	async function runConfirm() {
		if (!confirmTarget) return;
		confirming = true;
		const u = confirmTarget;
		try {
			if (confirmKind === 'delete') {
				await api.users.remove(u.id);
				users = users.filter((x) => x.id !== u.id);
				toast.success(`Deleted ${u.username}`);
			} else if (confirmKind === 'resetMfa') {
				await api.users.resetMfa(u.id);
				users = users.map((x) => (x.id === u.id ? { ...x, totp_enabled: false } : x));
				toast.success(`MFA reset for ${u.username}`);
			} else {
				const updated = await api.users.update(u.id, { is_active: confirmKind === 'activate' });
				users = users.map((x) => (x.id === updated.id ? updated : x));
				toast.success(`${updated.username} ${updated.is_active ? 'activated' : 'deactivated'}`);
			}
			confirmOpen = false;
		} catch (err) {
			toast.error('Action failed', { description: toApiError(err).detail });
		} finally {
			confirming = false;
		}
	}

	function menuFor(u: User): MenuItem[] {
		const self = u.id === me?.id;
		return [
			{ label: 'Change role', onselect: () => openDialog('edit', u), disabled: self },
			{ label: 'Reset password', onselect: () => openDialog('password', u) },
			{ label: 'Reset MFA', onselect: () => ask('resetMfa', u), disabled: !u.totp_enabled },
			{
				label: u.is_active ? 'Deactivate' : 'Activate',
				onselect: () => ask(u.is_active ? 'deactivate' : 'activate', u),
				disabled: self,
				separator: true
			},
			{ label: 'Delete', danger: true, onselect: () => ask('delete', u), disabled: self }
		];
	}

	const columns: Column[] = [
		{ key: 'username', label: 'User' },
		{ key: 'role', label: 'Role' },
		{ key: 'status', label: 'Status' },
		{ key: 'mfa', label: 'MFA', class: 'hidden lg:table-cell' },
		{ key: 'last_login', label: 'Last sign-in', class: 'hidden lg:table-cell' },
		{ key: 'actions', label: 'Actions', srOnly: true, align: 'right', class: 'w-12' }
	];

	const CONFIRM_COPY = {
		delete: { title: 'Delete user?', message: 'The account and all its sessions and API keys are removed permanently.', label: 'Delete user', tone: 'danger' as const },
		deactivate: { title: 'Deactivate user?', message: 'The user is signed out everywhere and their API keys stop working. You can reactivate later.', label: 'Deactivate', tone: 'danger' as const },
		activate: { title: 'Activate user?', message: 'The user will be able to sign in again.', label: 'Activate', tone: 'primary' as const },
		resetMfa: { title: 'Reset MFA?', message: 'Two-factor authentication is removed; the user can sign in with only a password until they enrol again.', label: 'Reset MFA', tone: 'danger' as const }
	};
</script>

<Card title="Users" description="Admins manage everything; operators manage interfaces and peers; viewers are read-only." flush>
	{#snippet actions()}
		<Button size="sm" variant="primary" onclick={() => openDialog('create')}>
			<Plus class="h-4 w-4" aria-hidden="true" />
			New user
		</Button>
	{/snippet}

	{#if error}
		<ErrorState compact message={error} onretry={load} />
	{:else}
		<Table {columns} rows={users} rowKey={(u) => u.id} caption="Users" {loading} skeletonRows={3}>
			{#snippet cell(u, col)}
				{#if col.key === 'username'}
					<span class="font-medium text-fg">{u.username}</span>
					{#if u.id === me?.id}<span class="ml-2 text-[12px] text-fg-subtle">(you)</span>{/if}
				{:else if col.key === 'role'}
					<Badge tone={u.role === 'admin' ? 'accent' : 'neutral'} size="sm">{u.role}</Badge>
				{:else if col.key === 'status'}
					<Badge tone={u.is_active ? 'success' : 'warning'} size="sm">{u.is_active ? 'Active' : 'Inactive'}</Badge>
				{:else if col.key === 'mfa'}
					<span class="text-fg-muted">{u.totp_enabled ? 'Enabled' : 'Off'}</span>
				{:else if col.key === 'last_login'}
					<span class="text-fg-muted" title={formatDateTime(u.last_login_at)}>{u.last_login_at ? formatRelative(u.last_login_at) : 'Never'}</span>
				{:else if col.key === 'actions'}
					<div class="flex justify-end">
						<DropdownMenu items={menuFor(u)} label={`Actions for ${u.username}`}>
							{#snippet trigger({ toggle, props })}
								<IconButton label={`Actions for ${u.username}`} size="sm" onclick={toggle} {...props}>
									<MoreHorizontal class="h-4 w-4" />
								</IconButton>
							{/snippet}
						</DropdownMenu>
					</div>
				{/if}
			{/snippet}
			{#snippet card(u)}
				<div class="flex items-start justify-between gap-3">
					<div class="text-sm">
						<p class="font-medium text-fg">{u.username} {#if u.id === me?.id}<span class="text-[12px] text-fg-subtle">(you)</span>{/if}</p>
						<p class="mt-1 flex flex-wrap gap-1.5">
							<Badge tone={u.role === 'admin' ? 'accent' : 'neutral'} size="sm">{u.role}</Badge>
							<Badge tone={u.is_active ? 'success' : 'warning'} size="sm">{u.is_active ? 'Active' : 'Inactive'}</Badge>
							{#if u.totp_enabled}<Badge tone="info" size="sm">MFA</Badge>{/if}
						</p>
					</div>
					<DropdownMenu items={menuFor(u)} label={`Actions for ${u.username}`}>
						{#snippet trigger({ toggle, props })}
							<IconButton label={`Actions for ${u.username}`} onclick={toggle} {...props}>
								<MoreHorizontal class="h-4 w-4" />
							</IconButton>
						{/snippet}
					</DropdownMenu>
				</div>
			{/snippet}
			{#snippet empty()}
				<EmptyState compact title="No users" description="Create the first additional user.">
					{#snippet icon()}<Users class="h-6 w-6" />{/snippet}
				</EmptyState>
			{/snippet}
		</Table>
	{/if}
</Card>

<Dialog
	bind:open={dialogOpen}
	title={mode === 'create' ? 'New user' : mode === 'edit' ? `Change role for ${target?.username}` : `Reset password for ${target?.username}`}
	size="sm"
	locked={saving}
>
	<form
		id="user-form"
		class="flex flex-col gap-4"
		onsubmit={(e) => {
			e.preventDefault();
			void save();
		}}
	>
		{#if formError}
			<Alert tone="danger">{formError}</Alert>
		{/if}
		{#if mode === 'create'}
			<Input label="Username" bind:value={username} required autocomplete="off" error={touched ? errors.username : null} />
		{/if}
		{#if mode !== 'edit'}
			<Input label={mode === 'create' ? 'Password' : 'New password'} type="password" autocomplete="new-password" bind:value={password} hint="10–128 characters." error={touched ? errors.password : null} />
		{/if}
		{#if mode !== 'password'}
			<Select label="Role" bind:value={role} options={ROLES} />
		{/if}
	</form>
	{#snippet footer()}
		<Button variant="ghost" onclick={() => (dialogOpen = false)} disabled={saving}>Cancel</Button>
		<Button variant="primary" type="submit" form="user-form" loading={saving}>
			{mode === 'create' ? 'Create user' : 'Save'}
		</Button>
	{/snippet}
</Dialog>

<ConfirmDialog
	bind:open={confirmOpen}
	title={CONFIRM_COPY[confirmKind].title}
	message={CONFIRM_COPY[confirmKind].message}
	confirmLabel={CONFIRM_COPY[confirmKind].label}
	tone={CONFIRM_COPY[confirmKind].tone}
	confirmText={confirmKind === 'delete' ? confirmTarget?.username : undefined}
	loading={confirming}
	onconfirm={runConfirm}
/>
