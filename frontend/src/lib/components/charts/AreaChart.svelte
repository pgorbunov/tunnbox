<script lang="ts">
	/**
	 * Two-series (Download / Upload) time-series area chart. Built to the dataviz
	 * skill's spec: fixed categorical pair (validated in both themes), 2px lines,
	 * ~10% area wash, hairline solid grid, legend + selective direct end labels,
	 * crosshair tooltip listing every series, keyboard navigation, table view.
	 */
	import { Table2, TrendingUp } from 'lucide-svelte';
	import {
		formatAxisTick,
		formatBytes,
		formatDateTime,
		formatRate,
		formatTooltipTime,
		parseDate
	} from '$lib/utils/format';
	import { uid } from '$lib/utils/dom';
	import IconButton from '$lib/components/ui/IconButton.svelte';
	import Skeleton from '$lib/components/ui/Skeleton.svelte';

	export interface ChartPoint {
		ts: string;
		rx: number;
		tx: number;
	}

	interface Props {
		points: ChartPoint[];
		/** Seconds per bucket; inferred from timestamps when omitted. */
		bucketSeconds?: number;
		title: string;
		loading?: boolean;
		refreshing?: boolean;
		height?: number;
		/** Show values as bytes per bucket instead of bytes per second. */
		mode?: 'rate' | 'volume';
	}

	let {
		points,
		bucketSeconds,
		title,
		loading = false,
		refreshing = false,
		height = 240,
		mode = 'rate'
	}: Props = $props();

	const id = uid('chart');
	let container: HTMLDivElement | null = $state(null);
	let width = $state(600);
	let hover = $state<number | null>(null);
	let focused = $state<number | null>(null);
	let tableView = $state(false);
	let hasFocus = $state(false);

	const M = { top: 12, right: 72, bottom: 26, left: 60 };

	$effect(() => {
		if (!container) return;
		const ro = new ResizeObserver((entries) => {
			const w = entries[0]?.contentRect.width;
			if (w && w > 0) width = w;
		});
		ro.observe(container);
		return () => ro.disconnect();
	});

	const times = $derived(points.map((p) => parseDate(p.ts)?.getTime() ?? 0));

	const bucket = $derived.by(() => {
		if (bucketSeconds && bucketSeconds > 0) return bucketSeconds;
		if (times.length < 2) return 0;
		const gaps: number[] = [];
		for (let i = 1; i < times.length; i++) gaps.push((times[i] - times[i - 1]) / 1000);
		gaps.sort((a, b) => a - b);
		return gaps[Math.floor(gaps.length / 2)] || 0;
	});

	const asRate = $derived(mode === 'rate' && bucket > 0);
	const scale = $derived(asRate ? 1 / bucket : 1);
	const rx = $derived(points.map((p) => Math.max(0, p.rx) * scale));
	const tx = $derived(points.map((p) => Math.max(0, p.tx) * scale));
	const fmt = $derived(asRate ? formatRate : formatBytes);

	const enough = $derived(points.length >= 2 && width > 0);

	const plotW = $derived(Math.max(10, width - M.left - M.right));
	const plotH = $derived(height - M.top - M.bottom);

	const xMin = $derived(times[0] ?? 0);
	const xMax = $derived(times[times.length - 1] ?? 1);
	const xSpan = $derived(Math.max(1, xMax - xMin));

	/** Nice upper bound and ticks in byte-friendly steps (1, 2, 5 × 1024^k). */
	const yAxis = $derived.by(() => {
		const max = Math.max(1, ...rx, ...tx);
		let unit = 1;
		while (max / unit >= 1024 && unit < 1024 ** 5) unit *= 1024;
		const rel = max / unit; // 1..1024
		const candidates = [1, 2, 2.5, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000];
		let step = candidates[candidates.length - 1];
		for (const c of candidates) {
			if (rel / c <= 4) {
				step = c;
				break;
			}
		}
		const top = Math.ceil(rel / step) * step * unit;
		const ticks: number[] = [];
		for (let v = 0; v <= top + 1e-9; v += step * unit) ticks.push(v);
		return { top: top || 1, ticks };
	});

	const x = (i: number) => M.left + ((times[i] - xMin) / xSpan) * plotW;
	const y = (v: number) => M.top + plotH - (v / yAxis.top) * plotH;

	function linePath(values: number[]): string {
		if (!enough) return '';
		return values.map((v, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
	}
	function areaPath(values: number[]): string {
		if (!enough) return '';
		const base = (M.top + plotH).toFixed(1);
		return `${linePath(values)} L${x(values.length - 1).toFixed(1)},${base} L${x(0).toFixed(1)},${base} Z`;
	}

	const rxLine = $derived(linePath(rx));
	const txLine = $derived(linePath(tx));
	const rxArea = $derived(areaPath(rx));
	const txArea = $derived(areaPath(tx));

	const xTicks = $derived.by(() => {
		if (!enough) return [] as { x: number; label: string }[];
		const count = Math.max(2, Math.min(8, Math.floor(plotW / 110)));
		const spanMs = xMax - xMin;
		const out: { x: number; label: string }[] = [];
		for (let k = 0; k < count; k++) {
			const t = xMin + (spanMs * k) / (count - 1);
			const label = formatAxisTick(new Date(t), spanMs);
			// Drop ticks whose formatted label repeats the previous one (short spans can
			// otherwise render several ticks with identical hour:minute text).
			if (out.length > 0 && out[out.length - 1].label === label) continue;
			out.push({ x: M.left + (plotW * k) / (count - 1), label });
		}
		return out;
	});

	const active = $derived(hover ?? (hasFocus ? focused : null));

	function indexAt(clientX: number): number {
		if (!container) return 0;
		const rect = container.getBoundingClientRect();
		const px = clientX - rect.left - M.left;
		const t = xMin + (px / plotW) * xSpan;
		let best = 0;
		let bestD = Infinity;
		for (let i = 0; i < times.length; i++) {
			const d = Math.abs(times[i] - t);
			if (d < bestD) {
				bestD = d;
				best = i;
			}
		}
		return best;
	}

	function onpointermove(e: PointerEvent) {
		if (!enough) return;
		hover = indexAt(e.clientX);
	}
	function onpointerleave() {
		hover = null;
	}
	function onkeydown(e: KeyboardEvent) {
		if (!enough) return;
		const n = points.length;
		const cur = focused ?? n - 1;
		if (e.key === 'ArrowLeft') {
			e.preventDefault();
			focused = Math.max(0, cur - 1);
		} else if (e.key === 'ArrowRight') {
			e.preventDefault();
			focused = Math.min(n - 1, cur + 1);
		} else if (e.key === 'Home') {
			e.preventDefault();
			focused = 0;
		} else if (e.key === 'End') {
			e.preventDefault();
			focused = n - 1;
		} else if (e.key === 'Escape') {
			focused = null;
		}
	}

	const tooltipLeft = $derived.by(() => {
		if (active === null) return 0;
		const px = x(active);
		const flip = px > width - 190;
		return flip ? px - 12 - 170 : px + 12;
	});

	const last = $derived(points.length - 1);
	const summary = $derived(
		enough
			? `${title}: ${points.length} points from ${formatTooltipTime(points[0].ts, xSpan)} to ${formatTooltipTime(points[last].ts, xSpan)}. Latest download ${fmt(rx[last])}, upload ${fmt(tx[last])}.`
			: `${title}: no data`
	);

	const valueText = $derived.by(() => {
		const i = active ?? last;
		if (!enough || i < 0) return '';
		return `${formatTooltipTime(points[i].ts, xSpan)}: download ${fmt(rx[i])}, upload ${fmt(tx[i])}`;
	});

	// Keep end labels from colliding: if too close, nudge apart.
	const endLabels = $derived.by(() => {
		if (!enough) return { rx: 0, tx: 0 };
		let a = y(rx[last]);
		let b = y(tx[last]);
		if (Math.abs(a - b) < 14) {
			const mid = (a + b) / 2;
			if (a <= b) {
				a = mid - 7;
				b = mid + 7;
			} else {
				a = mid + 7;
				b = mid - 7;
			}
		}
		return { rx: a, tx: b };
	});
</script>

<div class="flex min-w-0 flex-col gap-3">
	<div class="flex flex-wrap items-center justify-between gap-2">
		<ul class="flex items-center gap-4 text-[13px] text-fg-muted" aria-label="Series">
			<li class="flex items-center gap-2">
				<span class="inline-block h-0.5 w-4 rounded-full bg-chart-download" aria-hidden="true"></span>
				Download
			</li>
			<li class="flex items-center gap-2">
				<span class="inline-block h-0.5 w-4 rounded-full bg-chart-upload" aria-hidden="true"></span>
				Upload
			</li>
			{#if asRate}
				<li class="text-fg-subtle">per second</li>
			{/if}
		</ul>
		<IconButton
			label={tableView ? 'Show chart' : 'Show as table'}
			size="sm"
			variant="outline"
			active={tableView}
			onclick={() => (tableView = !tableView)}
		>
			{#if tableView}<TrendingUp class="h-4 w-4" />{:else}<Table2 class="h-4 w-4" />{/if}
		</IconButton>
	</div>

	{#if loading && points.length === 0}
		<Skeleton class="w-full" rounded="md" />
		<div style={`height:${height}px`} class="skeleton rounded-md"></div>
	{:else if tableView}
		<div class="max-h-[320px] overflow-auto rounded-md border border-border scrollbar-thin">
			<table class="w-full text-[13px]">
				<caption class="sr-only">{title}</caption>
				<thead class="sticky top-0 bg-bg-subtle text-left text-xs tracking-wide text-fg-subtle uppercase">
					<tr>
						<th scope="col" class="px-3 py-2 font-semibold">Time</th>
						<th scope="col" class="px-3 py-2 text-right font-semibold">Download</th>
						<th scope="col" class="px-3 py-2 text-right font-semibold">Upload</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-border">
					{#each points as p, i (p.ts)}
						<tr>
							<td class="px-3 py-1.5 text-fg-muted">{formatDateTime(p.ts)}</td>
							<td class="px-3 py-1.5 text-right text-fg tabular">{fmt(rx[i])}</td>
							<td class="px-3 py-1.5 text-right text-fg tabular">{fmt(tx[i])}</td>
						</tr>
					{:else}
						<tr><td colspan="3" class="px-3 py-6 text-center text-fg-muted">No data yet</td></tr>
					{/each}
				</tbody>
			</table>
		</div>
	{:else}
		<div
			bind:this={container}
			class={`relative w-full min-w-0 overflow-hidden transition-opacity duration-200 select-none ${refreshing ? 'opacity-70' : ''}`}
			style={`height:${height}px`}
		>
			{#if !enough}
				<div
					class="absolute inset-0 flex items-center justify-center rounded-md border border-dashed border-border text-sm text-fg-subtle"
				>
					Not enough data yet — stats appear after a couple of samples.
				</div>
			{:else}
				<!-- The crosshair is a slider over time: arrows move it, aria-valuetext reads both series. -->
				<div
					role="slider"
					tabindex="0"
					aria-label={`${title} — move through time`}
					aria-valuemin={0}
					aria-valuemax={last}
					aria-valuenow={active ?? last}
					aria-valuetext={valueText}
					aria-describedby={`${id}-summary`}
					class="absolute inset-0 rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring"
					{onpointermove}
					{onpointerleave}
					{onkeydown}
					onfocus={() => {
						hasFocus = true;
						if (focused === null) focused = last;
					}}
					onblur={() => (hasFocus = false)}
				></div>
				<p id={`${id}-summary`} class="sr-only">{summary}</p>
				<svg
					{height}
					viewBox={`0 0 ${width} ${height}`}
					preserveAspectRatio="none"
					aria-hidden="true"
					class="pointer-events-none block w-full overflow-visible"
				>
					<defs>
						<clipPath id={`${id}-clip`}>
							<rect x={M.left} y={M.top} width={plotW} height={plotH} />
						</clipPath>
					</defs>

					<!-- grid + y ticks -->
					{#each yAxis.ticks as t (t)}
						<line
							x1={M.left}
							x2={M.left + plotW}
							y1={y(t)}
							y2={y(t)}
							stroke="var(--chart-grid)"
							stroke-width="1"
							shape-rendering="crispEdges"
						/>
						<text
							x={M.left - 8}
							y={y(t)}
							text-anchor="end"
							dominant-baseline="middle"
							class="fill-fg-subtle text-[11px] tabular"
						>
							{t === 0 ? '0' : fmt(t).replace('.0 ', ' ')}
						</text>
					{/each}
					<!-- x ticks -->
					{#each xTicks as t, i (i)}
						<text
							x={t.x}
							y={height - 6}
							text-anchor={i === 0 ? 'start' : i === xTicks.length - 1 ? 'end' : 'middle'}
							class="fill-fg-subtle text-[11px]"
						>
							{t.label}
						</text>
					{/each}

					<g clip-path={`url(#${id}-clip)`}>
						<path d={rxArea} fill="var(--chart-download)" fill-opacity="0.1" />
						<path d={txArea} fill="var(--chart-upload)" fill-opacity="0.1" />
						<path
							d={rxLine}
							fill="none"
							stroke="var(--chart-download)"
							stroke-width="2"
							stroke-linejoin="round"
							stroke-linecap="round"
						/>
						<path
							d={txLine}
							fill="none"
							stroke="var(--chart-upload)"
							stroke-width="2"
							stroke-linejoin="round"
							stroke-linecap="round"
						/>
					</g>

					<!-- direct end labels (text in ink, colored key beside it) -->
					<g class="text-[11px]">
						<circle
							cx={x(last)}
							cy={y(rx[last])}
							r="4"
							fill="var(--chart-download)"
							stroke="var(--surface)"
							stroke-width="2"
						/>
						<text x={x(last) + 8} y={endLabels.rx} dominant-baseline="middle" class="fill-fg-muted tabular"
							>{fmt(rx[last])}</text
						>
						<circle
							cx={x(last)}
							cy={y(tx[last])}
							r="4"
							fill="var(--chart-upload)"
							stroke="var(--surface)"
							stroke-width="2"
						/>
						<text x={x(last) + 8} y={endLabels.tx} dominant-baseline="middle" class="fill-fg-muted tabular"
							>{fmt(tx[last])}</text
						>
					</g>

					<!-- crosshair -->
					{#if active !== null}
						<line
							x1={x(active)}
							x2={x(active)}
							y1={M.top}
							y2={M.top + plotH}
							stroke="var(--border-strong)"
							stroke-width="1"
						/>
						<circle
							cx={x(active)}
							cy={y(rx[active])}
							r="4.5"
							fill="var(--chart-download)"
							stroke="var(--surface)"
							stroke-width="2"
						/>
						<circle
							cx={x(active)}
							cy={y(tx[active])}
							r="4.5"
							fill="var(--chart-upload)"
							stroke="var(--surface)"
							stroke-width="2"
						/>
					{/if}
				</svg>

				{#if active !== null}
					<div
						class="pointer-events-none absolute top-2 z-10 w-[170px] rounded-md border border-border bg-surface-raised p-2.5 text-xs shadow-md"
						style={`left:${tooltipLeft}px`}
						role="status"
					>
						<p class="mb-1.5 text-fg-subtle">{formatTooltipTime(points[active].ts, xSpan)}</p>
						<div class="flex items-center justify-between gap-2">
							<span class="flex items-center gap-1.5 text-fg-muted"
								><span class="inline-block h-0.5 w-3 bg-chart-download" aria-hidden="true"
								></span>Download</span
							>
							<span class="font-semibold text-fg tabular">{fmt(rx[active])}</span>
						</div>
						<div class="mt-1 flex items-center justify-between gap-2">
							<span class="flex items-center gap-1.5 text-fg-muted"
								><span class="inline-block h-0.5 w-3 bg-chart-upload" aria-hidden="true"></span>Upload</span
							>
							<span class="font-semibold text-fg tabular">{fmt(tx[active])}</span>
						</div>
					</div>
				{/if}
			{/if}
		</div>
	{/if}
</div>
