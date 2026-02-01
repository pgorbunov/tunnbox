<script lang="ts">
	import { RefreshCw } from 'lucide-svelte';

	interface Props {
		active: boolean;
	}

	let { active }: Props = $props();
</script>

{#if active}
	<div class="flex items-center gap-2 text-xs text-slate-400">
		<RefreshCw class="h-3 w-3 animate-spin" />
		<span>Refreshing...</span>
	</div>
{/if}
