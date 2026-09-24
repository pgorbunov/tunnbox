<script lang="ts">
	import type { Snippet } from 'svelte';
	import Skeleton from './Skeleton.svelte';

	interface Props {
		label: string;
		value: string | number | null | undefined;
		/** Secondary text after the value, e.g. "/ 12". */
		suffix?: string;
		hint?: string;
		loading?: boolean;
		tone?: 'default' | 'success' | 'warning' | 'danger' | 'download' | 'upload';
		icon?: Snippet;
		trend?: Snippet;
		href?: string;
	}

	let { label, value, suffix, hint, loading = false, tone = 'default', icon, trend, href }: Props = $props();

	const ICON_TONE = {
		default: 'bg-bg-subtle text-fg-muted',
		success: 'bg-success-soft text-success',
		warning: 'bg-warning-soft text-warning',
		danger: 'bg-danger-soft text-danger',
		download: 'bg-chart-download/15 text-chart-download',
		upload: 'bg-chart-upload/15 text-chart-upload'
	} as const;
</script>

<svelte:element
	this={href ? 'a' : 'div'}
	{href}
	class={`flex min-w-0 flex-col gap-2 rounded-lg border border-border bg-surface p-4 shadow-sm ${href ? 'transition-colors hover:border-border-strong' : ''}`}
>
	<div class="flex items-center justify-between gap-2">
		<span class="truncate text-[13px] font-medium text-fg-muted">{label}</span>
		{#if icon}
			<span
				class={`flex h-7 w-7 shrink-0 items-center justify-center rounded-md ${ICON_TONE[tone]}`}
				aria-hidden="true"
			>
				{@render icon()}
			</span>
		{/if}
	</div>
	{#if loading}
		<Skeleton class="h-8 w-24" />
	{:else}
		<div class="flex items-baseline gap-1.5">
			<span class="truncate text-2xl leading-none font-semibold text-fg">{value ?? '—'}</span>
			{#if suffix}
				<span class="text-sm text-fg-subtle">{suffix}</span>
			{/if}
		</div>
	{/if}
	{#if trend}
		<div class="-mb-1">{@render trend()}</div>
	{:else if hint}
		<p class="text-xs text-fg-subtle">{hint}</p>
	{/if}
</svelte:element>
