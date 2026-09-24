<script module lang="ts">
	export interface Segment<V extends string> {
		value: V;
		label: string;
		disabled?: boolean;
	}
</script>

<script lang="ts" generics="T extends string">
	import { uid } from '$lib/utils/dom';

	interface Props {
		value: T;
		options: Segment<T>[];
		label: string;
		size?: 'sm' | 'md';
		block?: boolean;
		onchange?: (value: T) => void;
	}

	let { value = $bindable(), options, label, size = 'sm', block = false, onchange }: Props = $props();

	const id = uid('seg');
	let buttons: (HTMLButtonElement | null)[] = $state([]);

	function select(v: T) {
		if (v === value) return;
		value = v;
		onchange?.(v);
	}

	function onkeydown(e: KeyboardEvent, i: number) {
		if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight' && e.key !== 'Home' && e.key !== 'End') return;
		e.preventDefault();
		let next = i;
		if (e.key === 'ArrowLeft') next = (i - 1 + options.length) % options.length;
		if (e.key === 'ArrowRight') next = (i + 1) % options.length;
		if (e.key === 'Home') next = 0;
		if (e.key === 'End') next = options.length - 1;
		select(options[next].value);
		buttons[next]?.focus();
	}
</script>

<div
	role="radiogroup"
	aria-label={label}
	class={`inline-flex rounded-md border border-border bg-bg-subtle p-0.5 ${block ? 'w-full' : ''}`}
>
	{#each options as opt, i (opt.value)}
		<button
			type="button"
			role="radio"
			id={`${id}-${opt.value}`}
			aria-checked={value === opt.value}
			tabindex={value === opt.value ? 0 : -1}
			disabled={opt.disabled}
			bind:this={buttons[i]}
			onclick={() => select(opt.value)}
			onkeydown={(e) => onkeydown(e, i)}
			class={`flex-1 rounded-[5px] font-medium whitespace-nowrap transition-colors duration-150 disabled:opacity-50
				${size === 'sm' ? 'h-7 px-2.5 text-[13px]' : 'h-9 px-3.5 text-sm'}
				${value === opt.value ? 'bg-surface text-fg shadow-sm' : 'text-fg-muted hover:text-fg'}`}
		>
			{opt.label}
		</button>
	{/each}
</div>
