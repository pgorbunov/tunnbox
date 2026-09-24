<script lang="ts">
	/** Tiny inline trend line (single series, no axes). */
	interface Props {
		values: number[];
		width?: number;
		height?: number;
		tone?: 'download' | 'upload' | 'accent' | 'muted';
		label: string;
	}

	let { values, width = 96, height = 28, tone = 'accent', label }: Props = $props();

	const COLORS = {
		download: 'var(--chart-download)',
		upload: 'var(--chart-upload)',
		accent: 'var(--accent)',
		muted: 'var(--fg-subtle)'
	} as const;

	const path = $derived.by(() => {
		if (values.length < 2) return '';
		const max = Math.max(1, ...values);
		const stepX = width / (values.length - 1);
		return values
			.map((v, i) => `${i === 0 ? 'M' : 'L'}${(i * stepX).toFixed(1)},${(height - 2 - (v / max) * (height - 4)).toFixed(1)}`)
			.join(' ');
	});
	const area = $derived(path ? `${path} L${width},${height} L0,${height} Z` : '');
</script>

<svg {width} {height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label} class="block overflow-visible">
	{#if path}
		<path d={area} fill={COLORS[tone]} fill-opacity="0.1" />
		<path d={path} fill="none" stroke={COLORS[tone]} stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round" />
	{:else}
		<line x1="0" x2={width} y1={height - 2} y2={height - 2} stroke="var(--border)" stroke-width="1" />
	{/if}
</svg>
