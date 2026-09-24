/** Input validators. Each returns an error message string, or null when valid. */

const IPV4_RE = /^(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}$/;

export function isIPv4(s: string): boolean {
	return IPV4_RE.test(s);
}

export function isIPv6(s: string): boolean {
	if (!s || s.length > 45) return false;
	const zoneless = s.split('%')[0];
	const halves = zoneless.split('::');
	if (halves.length > 2) return false;
	const groupsOf = (part: string) => (part === '' ? [] : part.split(':'));
	const head = groupsOf(halves[0]);
	const tail = halves.length === 2 ? groupsOf(halves[1]) : [];
	let count = 0;
	for (const [i, g] of [...head, ...tail].entries()) {
		const isLast = i === head.length + tail.length - 1;
		if (isLast && g.includes('.')) {
			if (!isIPv4(g)) return false;
			count += 2;
			continue;
		}
		if (!/^[0-9a-fA-F]{1,4}$/.test(g)) return false;
		count++;
	}
	if (halves.length === 2) return count < 8;
	return count === 8;
}

export function isIP(s: string): boolean {
	return isIPv4(s) || isIPv6(s);
}

export function isCIDR(s: string, opts: { requirePrefix?: boolean } = {}): boolean {
	const [ip, prefix, ...rest] = s.split('/');
	if (rest.length) return false;
	if (prefix === undefined) return !opts.requirePrefix && isIP(ip);
	if (!/^\d{1,3}$/.test(prefix)) return false;
	const p = Number(prefix);
	if (isIPv4(ip)) return p <= 32;
	if (isIPv6(ip)) return p <= 128;
	return false;
}

const HOSTNAME_RE = /^(?=.{1,253}$)(?!-)([a-zA-Z0-9-]{1,63}(?<!-)\.)*[a-zA-Z0-9-]{1,63}(?<!-)$/;

export function isHostname(s: string): boolean {
	return HOSTNAME_RE.test(s);
}

export function splitList(s: string): string[] {
	return s
		.split(/[,\s]+/)
		.map((x) => x.trim())
		.filter(Boolean);
}

// ---- Field validators (message | null) ------------------------------------

export function required(value: string, label = 'This field'): string | null {
	return value.trim() ? null : `${label} is required`;
}

export function validateInterfaceName(value: string): string | null {
	const v = value.trim();
	if (!v) return 'Name is required';
	if (!/^[a-zA-Z0-9_=+.-]{1,15}$/.test(v)) return 'Use 1–15 characters: letters, digits, _ = + . -';
	if (['all', 'default', 'lo'].includes(v)) return `"${v}" is reserved`;
	return null;
}

export function validatePeerName(value: string): string | null {
	const v = value.trim();
	if (!v) return 'Name is required';
	if (v.length > 64) return 'Keep it under 64 characters';
	return null;
}

/** Comma-separated list of CIDRs (prefix required). */
export function validateCidrList(
	value: string,
	opts: { requirePrefix?: boolean; allowEmpty?: boolean } = {}
): string | null {
	const items = splitList(value);
	if (items.length === 0) return opts.allowEmpty ? null : 'Enter at least one address';
	for (const item of items) {
		if (!isCIDR(item, { requirePrefix: opts.requirePrefix })) return `"${item}" is not a valid CIDR`;
	}
	return null;
}

/** Interface address: each entry must carry a prefix (e.g. 10.8.0.1/24). */
export function validateInterfaceAddress(value: string): string | null {
	const items = splitList(value);
	if (items.length === 0) return 'Address is required';
	for (const item of items) {
		if (!isCIDR(item, { requirePrefix: true }))
			return `"${item}" must be an IP with prefix, e.g. 10.8.0.1/24`;
		const [, prefix] = item.split('/');
		if (item.includes(':') ? Number(prefix) === 128 : Number(prefix) === 32)
			return `"${item}" has no room for peers — use a wider prefix`;
	}
	return null;
}

export function validatePort(value: string | number): string | null {
	const n = typeof value === 'number' ? value : Number(value);
	if (!Number.isInteger(n)) return 'Port must be a whole number';
	if (n < 1 || n > 65535) return 'Port must be between 1 and 65535';
	return null;
}

/** Comma-separated list of DNS server IPs; empty allowed. */
export function validateDnsList(value: string): string | null {
	const items = splitList(value);
	for (const item of items) {
		if (!isIP(item)) return `"${item}" is not a valid IP address`;
	}
	return null;
}

export function validateMtu(value: string | number | null): string | null {
	if (value === null || value === '') return null;
	const n = typeof value === 'number' ? value : Number(value);
	if (!Number.isInteger(n)) return 'MTU must be a whole number';
	if (n < 1280 || n > 1500) return 'MTU must be between 1280 and 1500';
	return null;
}

export function validateKeepalive(value: string | number): string | null {
	const n = typeof value === 'number' ? value : Number(value);
	if (!Number.isInteger(n)) return 'Keepalive must be a whole number';
	if (n < 0 || n > 65535) return 'Keepalive must be between 0 and 65535 seconds';
	return null;
}

/** Hostname or IP without a port. */
export function validateEndpoint(value: string, opts: { allowEmpty?: boolean } = {}): string | null {
	const v = value.trim();
	if (!v) return opts.allowEmpty ? null : 'Endpoint is required';
	if (isIPv4(v) || isHostname(v)) return null;
	if (v.startsWith('[') && v.endsWith(']') && isIPv6(v.slice(1, -1))) return null;
	if (isIPv6(v)) return null;
	if (/:\d+$/.test(v) && !isIPv6(v)) return 'Enter the host only — the port is added automatically';
	return 'Enter a valid hostname or IP address';
}

export function validateUsername(value: string): string | null {
	const v = value.trim();
	if (!v) return 'Username is required';
	if (v.length < 3) return 'At least 3 characters';
	if (v.length > 32) return 'At most 32 characters';
	if (!/^[a-zA-Z0-9._-]+$/.test(v)) return 'Letters, digits, dots, underscores and dashes only';
	return null;
}

export function validatePassword(value: string, username = ''): string | null {
	if (value.length < 10) return 'At least 10 characters';
	if (value.length > 128) return 'At most 128 characters';
	if (username && value.toLowerCase() === username.toLowerCase()) return 'Password cannot equal the username';
	return null;
}

export function validateTotpOrRecovery(value: string): string | null {
	const v = value.trim();
	if (/^\d{6}$/.test(v)) return null;
	if (/^[a-zA-Z0-9]{4}-?[a-zA-Z0-9]{4}$/.test(v)) return null;
	return 'Enter a 6-digit code or a recovery code (xxxx-xxxx)';
}

export function isTotpCode(value: string): boolean {
	return /^\d{6}$/.test(value.trim());
}

export function isRecoveryCode(value: string): boolean {
	return /^[a-zA-Z0-9]{4}-[a-zA-Z0-9]{4}$/.test(value.trim());
}
