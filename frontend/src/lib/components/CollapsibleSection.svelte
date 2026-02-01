<script lang="ts">
	import { onMount } from 'svelte';
	import { ChevronDown } from 'lucide-svelte';
	import { slide } from 'svelte/transition';
	import type { ComponentType } from 'svelte';
	import type { Snippet } from 'svelte';

	interface Props {
		id: string;
		title: string;
		icon: ComponentType;
		iconColor: string;
		defaultExpanded?: boolean;
		children: Snippet;
	}

	let { id, title, icon: Icon, iconColor, defaultExpanded = true, children }: Props = $props();

	let expanded = $state(defaultExpanded);

	onMount(() => {
		// Load saved state from localStorage
		const saved = localStorage.getItem(`section-${id}-expanded`);
		if (saved !== null) {
			expanded = saved === 'true';
		}
	});

	function toggle() {
		expanded = !expanded;
		// Save state to localStorage
		localStorage.setItem(`section-${id}-expanded`, String(expanded));
	}
</script>

<div class="bg-white dark:bg-slate-800/50 rounded-xl border border-slate-200 dark:border-slate-700/50 overflow-hidden">
	<!-- Header (clickable) -->
	<button
		type="button"
		onclick={toggle}
		class="w-full p-6 flex items-center justify-between hover:bg-slate-50 dark:hover:bg-slate-800/70 transition-colors text-left"
		aria-expanded={expanded}
		aria-controls="section-{id}-content"
	>
		<div class="flex items-center gap-3">
			<div class="p-2 rounded-lg {iconColor}">
				<Icon class="h-5 w-5" />
			</div>
			<h2 class="text-lg font-semibold text-slate-900 dark:text-white">{title}</h2>
		</div>
		<ChevronDown
			class="h-5 w-5 text-slate-600 dark:text-slate-400 transition-transform duration-200 {expanded
				? 'transform rotate-180'
				: ''}"
		/>
	</button>

	<!-- Content (collapsible) -->
	{#if expanded}
		<div id="section-{id}-content" transition:slide={{ duration: 200 }} class="px-6 pb-6">
			{@render children()}
		</div>
	{/if}
</div>
