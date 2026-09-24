import type { Peer } from '$lib/api/types';

export type PeerAction = 'details' | 'qr' | 'download' | 'share' | 'edit' | 'toggle' | 'rotate' | 'delete';

export type PeerActionHandler = (action: PeerAction, peer: Peer) => void;
