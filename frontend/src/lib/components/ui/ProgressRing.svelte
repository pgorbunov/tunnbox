<script lang="ts">
	interface Props {
		/** 0..1 */
		value: number;
		size?: number;
		stroke?: number;
		tone?: 'accent' | 'success' | 'warning' | 'danger';
		label: string;
	}

	let { value, size = 40, stroke = 4, tone = 'accent', label }: Props = $props();

	const r = $derived((size - stroke) / 2);
	const c = $derived(2 * Math.PI * r);
	const clamped = $derived(Math.min(1, Math.max(0, value)));
	const TONES = { accent: 'text-accent', success: 'text-success', warning: 'text-warning', danger: 'text-danger' } as const;
</script>

<svg
	width={size}
	height={size}
	viewBox={`0 0 ${size} ${size}`}
	role="img"
	aria-label={`${label}: ${Math.round(clamped * 100)}%`}
	class={TONES[tone]}
>
	<circle cx={size / 2} cy={size / 2} {r} fill="none" stroke="var(--border)" stroke-width={stroke} />
	<circle
		cx={size / 2}
		cy={size / 2}
		{r}
		fill="none"
		stroke="currentColor"
		stroke-width={stroke}
		stroke-linecap="round"
		stroke-dasharray={c}
		stroke-dashoffset={c * (1 - clamped)}
		transform={`rotate(-90 ${size / 2} ${size / 2})`}
		class="transition-[stroke-dashoffset] duration-300"
	/>
</svg>
