/** Formatting helpers: bytes, time, durations, CIDR utilities. */

const BYTE_UNITS = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB'];

/** Binary units, 1 decimal (none for bytes). */
export function formatBytes(n: number | null | undefined): string {
	if (n === null || n === undefined || !Number.isFinite(n)) return '—';
	if (n < 1024) return `${Math.round(n)} B`;
	let v = n;
	let i = 0;
	while (v >= 1024 && i < BYTE_UNITS.length - 1) {
		v /= 1024;
		i++;
	}
	return `${v.toFixed(1)} ${BYTE_UNITS[i]}`;
}

/** Bytes per second, e.g. "1.2 MiB/s". */
export function formatRate(bytesPerSecond: number): string {
	if (!Number.isFinite(bytesPerSecond) || bytesPerSecond <= 0) return '0 B/s';
	return `${formatBytes(bytesPerSecond)}/s`;
}

/** Compact integer (1,284 / 12.9K / 4.2M). */
export function formatCompact(n: number): string {
	if (!Number.isFinite(n)) return '—';
	if (Math.abs(n) < 10_000) return n.toLocaleString();
	return new Intl.NumberFormat(undefined, { notation: 'compact', maximumFractionDigits: 1 }).format(n);
}

export function parseDate(iso: string | null | undefined): Date | null {
	if (!iso) return null;
	const d = new Date(iso);
	return Number.isNaN(d.getTime()) ? null : d;
}

const rtf = typeof Intl !== 'undefined' ? new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' }) : null;

/** "2 min ago", "in 3 days", "just now". */
export function formatRelative(iso: string | Date | null | undefined, now: number = Date.now()): string {
	const d = iso instanceof Date ? iso : parseDate(iso);
	if (!d) return 'never';
	const diff = d.getTime() - now; // negative = past
	const abs = Math.abs(diff);
	const s = Math.round(abs / 1000);
	if (s < 10) return diff <= 0 ? 'just now' : 'in a moment';
	const past = diff < 0;
	const fmt = (v: number, unit: Intl.RelativeTimeFormatUnit) =>
		rtf ? rtf.format(past ? -v : v, unit) : `${v} ${unit}${v === 1 ? '' : 's'} ${past ? 'ago' : 'from now'}`;
	if (s < 60) return fmt(s, 'second').replace('seconds', 'sec').replace('second', 'sec');
	const m = Math.round(s / 60);
	if (m < 60) return fmt(m, 'minute').replace('minutes', 'min').replace('minute', 'min');
	const h = Math.round(m / 60);
	if (h < 24) return fmt(h, 'hour');
	const days = Math.round(h / 24);
	if (days < 30) return fmt(days, 'day');
	const months = Math.round(days / 30);
	if (months < 12) return fmt(months, 'month');
	return fmt(Math.round(days / 365), 'year');
}

/** Locale date+time, e.g. "Sep 24, 2026, 14:03". */
export function formatDateTime(
	iso: string | Date | null | undefined,
	opts: Intl.DateTimeFormatOptions = {}
): string {
	const d = iso instanceof Date ? iso : parseDate(iso);
	if (!d) return '—';
	return d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short', ...opts });
}

export function formatDate(iso: string | Date | null | undefined): string {
	const d = iso instanceof Date ? iso : parseDate(iso);
	if (!d) return '—';
	return d.toLocaleDateString(undefined, { dateStyle: 'medium' });
}

export function formatTime(iso: string | Date | null | undefined): string {
	const d = iso instanceof Date ? iso : parseDate(iso);
	if (!d) return '—';
	return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
}

const MINUTE_MS = 60_000;
const HOUR_MS = 3_600_000;
const DAY_MS = 86_400_000;

/** Axis tick label chosen from the visible time span, so ticks never repeat unnecessarily. */
export function formatAxisTick(d: Date, spanMs: number): string {
	if (spanMs > 7 * DAY_MS) {
		return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(d);
	}
	if (spanMs > 2 * DAY_MS) {
		return new Intl.DateTimeFormat(undefined, {
			month: 'short',
			day: 'numeric',
			hour: '2-digit',
			minute: '2-digit'
		}).format(d);
	}
	if (spanMs > 3 * HOUR_MS) {
		return new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit' }).format(d);
	}
	return new Intl.DateTimeFormat(undefined, {
		hour: '2-digit',
		minute: '2-digit',
		second: spanMs < 10 * MINUTE_MS ? '2-digit' : undefined
	}).format(d);
}

/** Full-precision timestamp for tooltips/crosshairs; adds seconds when the visible span is short. */
export function formatTooltipTime(iso: string | Date | null | undefined, spanMs: number): string {
	const d = iso instanceof Date ? iso : parseDate(iso);
	if (!d) return '—';
	return new Intl.DateTimeFormat(undefined, {
		dateStyle: 'medium',
		timeStyle: spanMs < 10 * MINUTE_MS ? 'medium' : 'short'
	}).format(d);
}

/** "3d 4h", "12m 5s", "45s" */
export function formatDuration(seconds: number): string {
	if (!Number.isFinite(seconds) || seconds < 0) return '—';
	const s = Math.floor(seconds);
	const d = Math.floor(s / 86400);
	const h = Math.floor((s % 86400) / 3600);
	const m = Math.floor((s % 3600) / 60);
	const sec = s % 60;
	if (d > 0) return `${d}d ${h}h`;
	if (h > 0) return `${h}h ${m}m`;
	if (m > 0) return `${m}m ${sec}s`;
	return `${sec}s`;
}

/** Convert an ISO string to the value a `datetime-local` input expects (local time). */
export function toDatetimeLocal(iso: string | null | undefined): string {
	const d = parseDate(iso);
	if (!d) return '';
	const pad = (n: number) => String(n).padStart(2, '0');
	return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** Convert a `datetime-local` value (local) into an ISO UTC string. */
export function fromDatetimeLocal(value: string): string | null {
	if (!value) return null;
	const d = new Date(value);
	return Number.isNaN(d.getTime()) ? null : d.toISOString();
}

export function truncateMiddle(s: string, max = 20): string {
	if (s.length <= max) return s;
	const half = Math.floor((max - 1) / 2);
	return `${s.slice(0, half)}…${s.slice(s.length - half)}`;
}

export function pluralize(n: number, one: string, many = `${one}s`): string {
	return `${n.toLocaleString()} ${n === 1 ? one : many}`;
}

// ---- CIDR helpers --------------------------------------------------------

export function splitList(s: string | null | undefined): string[] {
	if (!s) return [];
	return s
		.split(/[,\s]+/)
		.map((x) => x.trim())
		.filter(Boolean);
}

export function joinList(items: string[]): string {
	return items.join(', ');
}

export function isIPv6(addr: string): boolean {
	return addr.includes(':');
}

function ipv4ToInt(ip: string): number | null {
	const parts = ip.split('.');
	if (parts.length !== 4) return null;
	let n = 0;
	for (const p of parts) {
		if (!/^\d{1,3}$/.test(p)) return null;
		const v = Number(p);
		if (v > 255) return null;
		n = n * 256 + v;
	}
	return n;
}

function intToIPv4(n: number): string {
	return [24, 16, 8, 0].map((s) => (n >>> s) & 255).join('.');
}

function ipv6ToBigInt(ip: string): bigint | null {
	const zoneless = ip.split('%')[0];
	const halves = zoneless.split('::');
	if (halves.length > 2) return null;
	const expand = (part: string) => (part === '' ? [] : part.split(':'));
	let head = expand(halves[0]);
	let tail = halves.length === 2 ? expand(halves[1]) : [];
	// embedded IPv4 in last group
	const fixV4 = (groups: string[]) => {
		const last = groups[groups.length - 1];
		if (last && last.includes('.')) {
			const v4 = ipv4ToInt(last);
			if (v4 === null) return null;
			groups.splice(groups.length - 1, 1, ((v4 >>> 16) & 0xffff).toString(16), (v4 & 0xffff).toString(16));
		}
		return groups;
	};
	const h = fixV4(head);
	const t = fixV4(tail);
	if (!h || !t) return null;
	head = h;
	tail = t;
	const missing = 8 - head.length - tail.length;
	if (missing < 0 || (halves.length === 1 && missing !== 0)) return null;
	const groups = [...head, ...Array<string>(halves.length === 2 ? missing : 0).fill('0'), ...tail];
	if (groups.length !== 8) return null;
	let n = 0n;
	for (const g of groups) {
		if (!/^[0-9a-fA-F]{1,4}$/.test(g)) return null;
		n = (n << 16n) | BigInt(parseInt(g, 16));
	}
	return n;
}

function bigIntToIPv6(n: bigint): string {
	const groups: string[] = [];
	for (let i = 7; i >= 0; i--) groups.push(((n >> BigInt(i * 16)) & 0xffffn).toString(16));
	// compress longest run of zeros
	let bestStart = -1;
	let bestLen = 0;
	let curStart = -1;
	let curLen = 0;
	groups.forEach((g, i) => {
		if (g === '0') {
			if (curStart === -1) curStart = i;
			curLen++;
			if (curLen > bestLen) {
				bestLen = curLen;
				bestStart = curStart;
			}
		} else {
			curStart = -1;
			curLen = 0;
		}
	});
	if (bestLen > 1) {
		const before = groups.slice(0, bestStart).join(':');
		const after = groups.slice(bestStart + bestLen).join(':');
		return `${before}::${after}`;
	}
	return groups.join(':');
}

/**
 * Given "10.8.0.1/24" return the network CIDR "10.8.0.0/24". Works for IPv6 too.
 * Returns null for unparsable input.
 */
export function cidrNetwork(cidr: string): string | null {
	const [ip, prefixStr] = cidr.trim().split('/');
	if (!ip) return null;
	if (isIPv6(ip)) {
		const prefix = prefixStr === undefined ? 128 : Number(prefixStr);
		if (!Number.isInteger(prefix) || prefix < 0 || prefix > 128) return null;
		const n = ipv6ToBigInt(ip);
		if (n === null) return null;
		const mask = prefix === 0 ? 0n : ((1n << 128n) - 1n) ^ ((1n << BigInt(128 - prefix)) - 1n);
		return `${bigIntToIPv6(n & mask)}/${prefix}`;
	}
	const prefix = prefixStr === undefined ? 32 : Number(prefixStr);
	if (!Number.isInteger(prefix) || prefix < 0 || prefix > 32) return null;
	const n = ipv4ToInt(ip);
	if (n === null) return null;
	const mask = prefix === 0 ? 0 : (0xffffffff << (32 - prefix)) >>> 0;
	return `${intToIPv4((n & mask) >>> 0)}/${prefix}`;
}

/** Network CIDRs for every address on an interface ("10.8.0.1/24, fd00::1/64"). */
export function interfaceSubnets(address: string): string[] {
	return splitList(address)
		.map(cidrNetwork)
		.filter((x): x is string => x !== null);
}

/** Strip the prefix length from a CIDR list for display ("10.8.0.2/32" -> "10.8.0.2"). */
export function stripPrefixes(list: string): string {
	return splitList(list)
		.map((c) => c.replace(/\/(32|128)$/, ''))
		.join(', ');
}

export const FULL_TUNNEL = '0.0.0.0/0, ::/0';
export const LAN_RANGES = ['10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'];

export function isFullTunnel(list: string): boolean {
	const items = splitList(list);
	return items.includes('0.0.0.0/0') || items.includes('::/0');
}
