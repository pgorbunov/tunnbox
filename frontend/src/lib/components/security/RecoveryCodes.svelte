<script lang="ts">
	/** Shows recovery codes once, with copy/download and an acknowledgement checkbox. */
	import { Download } from 'lucide-svelte';
	import Alert from '$lib/components/ui/Alert.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import Checkbox from '$lib/components/ui/Checkbox.svelte';
	import CopyButton from '$lib/components/ui/CopyButton.svelte';

	let { codes, acknowledged = $bindable(false) }: { codes: string[]; acknowledged: boolean } = $props();

	const text = $derived(codes.join('\n'));

	function download() {
		const blob = new Blob([`TunnBox recovery codes\n\n${text}\n`], { type: 'text/plain' });
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = 'tunnbox-recovery-codes.txt';
		a.style.display = 'none';
		document.body.appendChild(a);
		a.click();
		a.remove();
		setTimeout(() => URL.revokeObjectURL(url), 1000);
	}
</script>

<div class="flex flex-col gap-4">
	<Alert tone="warning" title="These codes are shown only once">
		Each code signs you in once if you lose your authenticator. Store them somewhere safe, like a password
		manager.
	</Alert>
	<ul
		class="grid grid-cols-2 gap-2 rounded-md border border-border bg-bg-subtle p-4 font-mono text-sm text-fg"
		aria-label="Recovery codes"
	>
		{#each codes as c (c)}
			<li class="tabular">{c}</li>
		{/each}
	</ul>
	<div class="flex flex-wrap gap-2">
		<CopyButton {text} label="Copy codes" variant="button" />
		<Button onclick={download}>
			<Download class="h-4 w-4" aria-hidden="true" />
			Download .txt
		</Button>
	</div>
	<Checkbox bind:checked={acknowledged} label="I have saved these recovery codes" />
</div>
