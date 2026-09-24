<script lang="ts">
	/** Settings: General | Security | API keys | Users (admin) | Data | Appearance | About, via ?tab=. */
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import {
		Database,
		Download,
		ExternalLink,
		Info,
		KeyRound,
		Palette,
		ShieldCheck,
		SlidersHorizontal,
		Users
	} from 'lucide-svelte';
	import { api, toApiError } from '$lib/api';
	import type { Settings, SettingsUpdateRequest, SystemInfo } from '$lib/api/types';
	import { auth } from '$lib/stores/auth.svelte';
	import { settingsStore, type Density } from '$lib/stores/settings.svelte';
	import { themeStore, type Theme } from '$lib/stores/theme.svelte';
	import { toast } from '$lib/stores/toast.svelte';
	import { formatBytes, formatDuration, joinList, splitList } from '$lib/utils/format';
	import {
		validateCidrList,
		validateDnsList,
		validateEndpoint,
		validateKeepalive,
		validateMtu
	} from '$lib/utils/validation';
	import PageHeader from '$lib/components/app/PageHeader.svelte';
	import ApiKeysPanel from '$lib/components/security/ApiKeysPanel.svelte';
	import MfaCard from '$lib/components/security/MfaCard.svelte';
	import PasswordChangeForm from '$lib/components/security/PasswordChangeForm.svelte';
	import SessionsList from '$lib/components/security/SessionsList.svelte';
	import UsersPanel from '$lib/components/security/UsersPanel.svelte';
	import Alert from '$lib/components/ui/Alert.svelte';
	import Badge from '$lib/components/ui/Badge.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import ErrorState from '$lib/components/ui/ErrorState.svelte';
	import Input from '$lib/components/ui/Input.svelte';
	import SegmentedControl from '$lib/components/ui/SegmentedControl.svelte';
	import Skeleton from '$lib/components/ui/Skeleton.svelte';
	import Switch from '$lib/components/ui/Switch.svelte';
	import Tabs from '$lib/components/ui/Tabs.svelte';

	type Tab = 'general' | 'security' | 'api-keys' | 'users' | 'data' | 'appearance' | 'about';
	const TAB_IDS: Tab[] = ['general', 'security', 'api-keys', 'users', 'data', 'appearance', 'about'];

	const isAdmin = $derived(auth.can('admin'));
	const tabs = $derived([
		{ id: 'general' as const, label: 'General', icon: SlidersHorizontal },
		{ id: 'security' as const, label: 'Security', icon: ShieldCheck },
		{ id: 'api-keys' as const, label: 'API keys', icon: KeyRound },
		{ id: 'users' as const, label: 'Users', icon: Users, hidden: !isAdmin },
		{ id: 'data' as const, label: 'Data', icon: Database },
		{ id: 'appearance' as const, label: 'Appearance', icon: Palette },
		{ id: 'about' as const, label: 'About', icon: Info }
	]);

	function tabFromUrl(): Tab {
		const t = page.url.searchParams.get('tab');
		return TAB_IDS.includes(t as Tab) ? (t as Tab) : 'general';
	}
	let tab = $state<Tab>(tabFromUrl());
	$effect(() => {
		tab = tabFromUrl();
	});
	function selectTab(t: Tab) {
		void goto(t === 'general' ? '/settings' : `/settings?tab=${t}`, {
			replaceState: true,
			noScroll: true,
			keepFocus: true
		});
	}

	// ---- server settings ------------------------------------------------
	let server = $state<Settings | null>(null);
	let loadError = $state<string | null>(null);
	let saving = $state(false);
	let formError = $state<string | null>(null);

	let endpoint = $state('');
	let dns = $state('');
	let mtu = $state('');
	let keepalive = $state('25');
	let clientRoutes = $state('');
	let auditRetention = $state('90');
	let statsRetention = $state('90');
	let uiRefresh = $state('10');

	function fill(s: Settings) {
		endpoint = s.public_endpoint ?? '';
		dns = s.default_dns ?? '';
		mtu = s.default_mtu === null ? '' : String(s.default_mtu);
		keepalive = String(s.default_keepalive);
		clientRoutes = s.default_client_allowed_ips;
		auditRetention = String(s.audit_retention_days);
		statsRetention = String(s.stats_retention_days);
		uiRefresh = String(s.ui_refresh_seconds);
	}

	async function loadServer() {
		loadError = null;
		try {
			server = await settingsStore.load(true);
			fill(server);
		} catch (err) {
			loadError = toApiError(err).detail;
		}
	}
	$effect(() => {
		void loadServer();
	});

	const generalErrors = $derived({
		endpoint: validateEndpoint(endpoint, { allowEmpty: true }),
		dns: validateDnsList(dns),
		mtu: validateMtu(mtu),
		keepalive: validateKeepalive(keepalive),
		clientRoutes: validateCidrList(clientRoutes)
	});
	const dataErrors = $derived({
		auditRetention:
			Number.isInteger(Number(auditRetention)) && Number(auditRetention) >= 1
				? null
				: 'Enter a whole number of days (≥ 1)',
		statsRetention:
			Number.isInteger(Number(statsRetention)) && Number(statsRetention) >= 1
				? null
				: 'Enter a whole number of days (≥ 1)',
		uiRefresh:
			Number.isInteger(Number(uiRefresh)) && Number(uiRefresh) >= 3 && Number(uiRefresh) <= 300
				? null
				: 'Between 3 and 300 seconds'
	});

	async function save(body: SettingsUpdateRequest, label: string) {
		saving = true;
		formError = null;
		try {
			const s = await api.settings.update(body);
			server = s;
			settingsStore.set(s);
			fill(s);
			toast.success(`${label} saved`);
		} catch (err) {
			formError = toApiError(err).detail;
		} finally {
			saving = false;
		}
	}

	function saveGeneral() {
		if (Object.values(generalErrors).some(Boolean)) return;
		void save(
			{
				public_endpoint: endpoint.trim(),
				default_dns: joinList(splitList(dns)),
				default_mtu: mtu.trim() ? Number(mtu) : null,
				default_keepalive: Number(keepalive),
				default_client_allowed_ips: joinList(splitList(clientRoutes))
			},
			'General settings'
		);
	}
	function saveData() {
		if (Object.values(dataErrors).some(Boolean)) return;
		void save(
			{
				audit_retention_days: Number(auditRetention),
				stats_retention_days: Number(statsRetention),
				ui_refresh_seconds: Number(uiRefresh)
			},
			'Data settings'
		);
	}

	// ---- data actions -----------------------------------------------------
	let exporting = $state(false);
	let backingUp = $state(false);
	async function exportJson() {
		exporting = true;
		try {
			await api.system.downloadExport();
			toast.success('Export downloaded');
		} catch (err) {
			toast.error('Export failed', { description: toApiError(err).detail });
		} finally {
			exporting = false;
		}
	}
	async function backup() {
		backingUp = true;
		try {
			await api.system.downloadBackup();
			toast.success('Backup downloaded');
		} catch (err) {
			toast.error('Backup failed', { description: toApiError(err).detail });
		} finally {
			backingUp = false;
		}
	}

	// ---- about ------------------------------------------------------------
	let info = $state<SystemInfo | null>(null);
	let infoError = $state<string | null>(null);
	async function loadInfo() {
		infoError = null;
		try {
			info = await api.system.info();
		} catch (err) {
			infoError = toApiError(err).detail;
		}
	}
	$effect(() => {
		if (tab === 'about' && !info) void loadInfo();
	});

	// ---- appearance -------------------------------------------------------
	const THEMES: { value: Theme; label: string }[] = [
		{ value: 'light', label: 'Light' },
		{ value: 'dark', label: 'Dark' },
		{ value: 'system', label: 'System' }
	];
	const DENSITIES: { value: Density; label: string }[] = [
		{ value: 'comfortable', label: 'Comfortable' },
		{ value: 'compact', label: 'Compact' }
	];
	let refreshOverride = $state(settingsStore.prefs.refreshSeconds !== null);
	let refreshSeconds = $state(
		String(settingsStore.prefs.refreshSeconds ?? settingsStore.server?.ui_refresh_seconds ?? 10)
	);
	function applyRefreshPref() {
		const n = Number(refreshSeconds);
		settingsStore.setPrefs({ refreshSeconds: refreshOverride && Number.isFinite(n) && n >= 3 ? n : null });
	}
</script>

<svelte:head>
	<title>Settings · TunnBox</title>
</svelte:head>

<PageHeader title="Settings">
	<Tabs {tabs} value={tab} onchange={selectTab} label="Settings sections" idPrefix="settings" />
</PageHeader>

<div class="flex flex-col gap-6">
	{#if tab === 'general'}
		<div id="settings-panel-general" role="tabpanel" aria-labelledby="settings-general">
			{#if loadError}
				<ErrorState message={loadError} onretry={loadServer} />
			{:else if !server}
				<Card><Skeleton class="h-40 w-full" rounded="md" /></Card>
			{:else}
				<Card
					title="Defaults for new peers and interfaces"
					description={isAdmin
						? 'These values pre-fill new interfaces and client configurations.'
						: 'Only admins can change these.'}
				>
					<form
						class="flex flex-col gap-5"
						onsubmit={(e) => {
							e.preventDefault();
							saveGeneral();
						}}
					>
						{#if formError}
							<Alert tone="danger">{formError}</Alert>
						{/if}
						<div class="grid gap-4 md:grid-cols-2">
							<Input
								label="Public endpoint"
								bind:value={endpoint}
								mono
								placeholder="vpn.example.com"
								hint="Hostname or IP clients connect to (no port)."
								disabled={!isAdmin}
								error={generalErrors.endpoint}
							/>
							<Input
								label="Default DNS"
								bind:value={dns}
								mono
								hint="Comma-separated IPs."
								disabled={!isAdmin}
								error={generalErrors.dns}
							/>
							<Input
								label="Default MTU"
								bind:value={mtu}
								type="number"
								inputmode="numeric"
								min="1280"
								max="1500"
								placeholder="Not set"
								hint="1280–1500; empty = WireGuard default."
								disabled={!isAdmin}
								error={generalErrors.mtu}
							/>
							<Input
								label="Default keepalive (s)"
								bind:value={keepalive}
								type="number"
								inputmode="numeric"
								min="0"
								max="65535"
								disabled={!isAdmin}
								error={generalErrors.keepalive}
							/>
						</div>
						<Input
							label="Default client routes (AllowedIPs)"
							bind:value={clientRoutes}
							mono
							hint="What new peers route through the tunnel by default. 0.0.0.0/0, ::/0 = full tunnel."
							disabled={!isAdmin}
							error={generalErrors.clientRoutes}
						/>
						{#if isAdmin}
							<div class="flex justify-end gap-2 border-t border-border pt-4">
								<Button variant="ghost" onclick={() => server && fill(server)} disabled={saving}>Reset</Button
								>
								<Button variant="primary" type="submit" loading={saving}>Save changes</Button>
							</div>
						{/if}
					</form>
				</Card>
			{/if}
		</div>
	{:else if tab === 'security'}
		<div
			id="settings-panel-security"
			role="tabpanel"
			aria-labelledby="settings-security"
			class="flex flex-col gap-6"
		>
			<PasswordChangeForm />
			<MfaCard />
			<SessionsList />
		</div>
	{:else if tab === 'api-keys'}
		<div id="settings-panel-api-keys" role="tabpanel" aria-labelledby="settings-api-keys">
			<ApiKeysPanel />
		</div>
	{:else if tab === 'users' && isAdmin}
		<div id="settings-panel-users" role="tabpanel" aria-labelledby="settings-users">
			<UsersPanel />
		</div>
	{:else if tab === 'data'}
		<div
			id="settings-panel-data"
			role="tabpanel"
			aria-labelledby="settings-data"
			class="grid gap-6 lg:grid-cols-2"
		>
			{#if loadError}
				<ErrorState message={loadError} onretry={loadServer} />
			{:else if !server}
				<Card><Skeleton class="h-40 w-full" rounded="md" /></Card>
			{:else}
				<Card
					title="Retention and refresh"
					description={isAdmin
						? 'Old audit entries and traffic samples are pruned hourly.'
						: 'Only admins can change these.'}
				>
					<form
						class="flex flex-col gap-4"
						onsubmit={(e) => {
							e.preventDefault();
							saveData();
						}}
					>
						{#if formError}
							<Alert tone="danger">{formError}</Alert>
						{/if}
						<Input
							label="Audit log retention (days)"
							bind:value={auditRetention}
							type="number"
							inputmode="numeric"
							min="1"
							disabled={!isAdmin}
							error={dataErrors.auditRetention}
						/>
						<Input
							label="Traffic stats retention (days)"
							bind:value={statsRetention}
							type="number"
							inputmode="numeric"
							min="1"
							disabled={!isAdmin}
							error={dataErrors.statsRetention}
						/>
						<Input
							label="UI refresh interval (seconds)"
							bind:value={uiRefresh}
							type="number"
							inputmode="numeric"
							min="3"
							max="300"
							hint="Default polling interval for dashboards and lists."
							disabled={!isAdmin}
							error={dataErrors.uiRefresh}
						/>
						{#if isAdmin}
							<div class="flex justify-end gap-2 border-t border-border pt-4">
								<Button variant="primary" type="submit" loading={saving}>Save changes</Button>
							</div>
						{/if}
					</form>
				</Card>
			{/if}
			{#if isAdmin}
				<Card
					title="Export and backup"
					description="Move your configuration to another server or keep an offline copy."
				>
					<div class="flex flex-col gap-4">
						<div
							class="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border p-3"
						>
							<div class="text-sm">
								<p class="font-medium text-fg">Export JSON</p>
								<p class="text-[13px] text-fg-subtle">
									Users, interfaces, peers, settings and audit log — without any private keys.
								</p>
							</div>
							<Button onclick={exportJson} loading={exporting}>
								<Download class="h-4 w-4" aria-hidden="true" />
								Export
							</Button>
						</div>
						<div
							class="flex flex-wrap items-center justify-between gap-3 rounded-md border border-warning/40 bg-warning-soft/40 p-3"
						>
							<div class="text-sm">
								<p class="font-medium text-fg">Download full backup</p>
								<p class="text-[13px] text-fg-muted">
									A tar.gz of the database and rendered configs. <strong>It contains private keys</strong> — store
									it encrypted.
								</p>
							</div>
							<Button onclick={backup} loading={backingUp}>
								<Download class="h-4 w-4" aria-hidden="true" />
								Backup
							</Button>
						</div>
					</div>
				</Card>
			{/if}
		</div>
	{:else if tab === 'appearance'}
		<div
			id="settings-panel-appearance"
			role="tabpanel"
			aria-labelledby="settings-appearance"
			class="grid gap-6 lg:grid-cols-2"
		>
			<Card title="Theme" description="Stored on this device.">
				<div class="flex flex-col gap-5">
					<SegmentedControl
						value={themeStore.theme}
						options={THEMES}
						label="Theme"
						size="md"
						onchange={(v) => themeStore.set(v)}
					/>
					<div>
						<p class="mb-2 text-sm font-medium text-fg">Density</p>
						<SegmentedControl
							value={settingsStore.prefs.density}
							options={DENSITIES}
							label="Density"
							size="md"
							onchange={(v) => settingsStore.setPrefs({ density: v })}
						/>
					</div>
					<Switch
						checked={settingsStore.prefs.sidebarCollapsed}
						label="Collapse sidebar to icons"
						onchange={(v) => settingsStore.setPrefs({ sidebarCollapsed: v })}
					/>
				</div>
			</Card>
			<Card title="Live refresh" description="Override the server-wide refresh interval on this device.">
				<div class="flex flex-col gap-4">
					<Switch
						bind:checked={refreshOverride}
						label="Use a custom interval"
						description={`Server default: ${settingsStore.server?.ui_refresh_seconds ?? 10}s`}
						onchange={applyRefreshPref}
					/>
					<Input
						label="Interval (seconds)"
						bind:value={refreshSeconds}
						type="number"
						inputmode="numeric"
						min="3"
						max="300"
						disabled={!refreshOverride}
						oninput={applyRefreshPref}
						class="max-w-xs"
					/>
				</div>
			</Card>
		</div>
	{:else if tab === 'about'}
		<div
			id="settings-panel-about"
			role="tabpanel"
			aria-labelledby="settings-about"
			class="grid gap-6 lg:grid-cols-2"
		>
			<Card title="System">
				{#if infoError}
					<ErrorState compact message={infoError} onretry={loadInfo} />
				{:else if !info}
					<Skeleton class="h-40 w-full" rounded="md" />
				{:else}
					<dl class="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
						<dt class="text-fg-subtle">Version</dt>
						<dd class="text-fg">TunnBox {info.version}</dd>
						<dt class="text-fg-subtle">Backend</dt>
						<dd class="flex items-center gap-2 text-fg">
							{info.backend_mode}
							{#if info.backend_mode === 'mock'}<Badge tone="warning" size="sm">Simulated</Badge>{/if}
						</dd>
						<dt class="text-fg-subtle">WireGuard</dt>
						<dd class="text-fg">
							{info.wireguard_version ?? 'Not available'}{info.kernel_module ? ' · kernel module' : ''}
						</dd>
						<dt class="text-fg-subtle">Host</dt>
						<dd class="font-mono text-[13px] text-fg">{info.hostname}</dd>
						<dt class="text-fg-subtle">OS</dt>
						<dd class="text-fg">{info.os}</dd>
						<dt class="text-fg-subtle">Python</dt>
						<dd class="text-fg">{info.python_version}</dd>
						<dt class="text-fg-subtle">Uptime</dt>
						<dd class="text-fg">{formatDuration(info.uptime_seconds)}</dd>
						<dt class="text-fg-subtle">Database</dt>
						<dd class="text-fg">{formatBytes(info.database_size_bytes)}</dd>
						<dt class="text-fg-subtle">Config path</dt>
						<dd class="font-mono text-[13px] text-fg">{info.config_path}</dd>
					</dl>
				{/if}
			</Card>
			<Card title="Resources">
				<ul class="flex flex-col gap-2 text-sm">
					<li>
						<a
							href="/api/docs"
							target="_blank"
							rel="noopener noreferrer"
							class="inline-flex items-center gap-1.5 text-accent hover:underline"
							>API documentation <ExternalLink class="h-3.5 w-3.5" aria-hidden="true" /></a
						>
					</li>
					<li>
						<a
							href="https://github.com/pgorbunov/tunnbox"
							target="_blank"
							rel="noopener noreferrer"
							class="inline-flex items-center gap-1.5 text-accent hover:underline"
							>GitHub repository <ExternalLink class="h-3.5 w-3.5" aria-hidden="true" /></a
						>
					</li>
					<li>
						<a
							href="https://github.com/pgorbunov/tunnbox/tree/main/docs"
							target="_blank"
							rel="noopener noreferrer"
							class="inline-flex items-center gap-1.5 text-accent hover:underline"
							>Documentation <ExternalLink class="h-3.5 w-3.5" aria-hidden="true" /></a
						>
					</li>
				</ul>
				<p class="mt-4 text-[13px] text-fg-subtle">
					Press <kbd class="rounded-sm border border-border bg-bg-subtle px-1 font-sans text-[11px]">?</kbd> anywhere
					for keyboard shortcuts.
				</p>
			</Card>
		</div>
	{/if}
</div>
