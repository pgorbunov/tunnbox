<script lang="ts">
	import { page } from '$app/state';
	import { ArrowLeft, Compass } from 'lucide-svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import Logo from '$lib/components/app/Logo.svelte';

	const title = $derived(page.status === 404 ? 'Page not found' : 'Something went wrong');
	const message = $derived(
		page.status === 404
			? 'The page you are looking for does not exist or has moved.'
			: page.error?.message || 'An unexpected error occurred.'
	);
</script>

<svelte:head>
	<title>{title} · TunnBox</title>
</svelte:head>

<div class="flex min-h-[60vh] flex-col items-center justify-center px-4 text-center">
	<Logo size={36} class="mb-8" />
	<div class="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-bg-subtle text-fg-subtle" aria-hidden="true">
		<Compass class="h-6 w-6" />
	</div>
	<p class="font-mono text-sm text-fg-subtle">{page.status}</p>
	<h1 class="mt-1 text-xl font-semibold text-fg">{title}</h1>
	<p class="mt-2 max-w-sm text-sm text-fg-muted">{message}</p>
	<div class="mt-6">
		<Button variant="primary" href="/">
			<ArrowLeft class="h-4 w-4" aria-hidden="true" />
			Back to dashboard
		</Button>
	</div>
</div>
