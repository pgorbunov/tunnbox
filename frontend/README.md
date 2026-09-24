# TunnBox frontend

SvelteKit 2 + Svelte 5 (runes) + Tailwind 4 single-page app, served by the FastAPI backend from
`frontend/build` with an `index.html` fallback. SSR and prerendering are off (`src/routes/+layout.ts`).

## Commands

| Command           | What it does                                                    |
| ----------------- | --------------------------------------------------------------- |
| `npm run dev`     | Vite dev server on :5173, proxies `/api` to `localhost:8000`    |
| `npm run check`   | `svelte-check` (must report 0 errors)                           |
| `npm run build`   | Production build into `build/` (adapter-static, SPA fallback)   |
| `npm run preview` | Serve the production build locally                              |
| `npm run format`  | Prettier (tabs, single quotes, Svelte + Tailwind class sorting) |
| `npm run lint`    | Prettier `--check`                                              |

## Structure

```
src/
  app.html                 Shell. No inline scripts (strict CSP); theme via CSS + class on <html>.
  app.css                  Tailwind 4 + design tokens (:root light, .dark, prefers-color-scheme fallback)
  lib/
    api/
      client.ts            fetch wrapper: in-memory access token, single-flight refresh, retry-once on 401,
                           AbortSignal, ApiError {status, detail, code}, text/blob/download helpers
      types.ts             TypeScript mirror of SPEC §2.7 (the binding contract)
      index.ts             typed endpoint groups: auth, mfa, apiKeys, users, interfaces, peers, share,
                           stats, audit, settings, system
    stores/                Svelte 5 rune stores (*.svelte.ts)
      auth.svelte.ts       user, status ('booting'|'anon'|'authed'|'setup'), login/loginMfa/setup/logout, can(role)
      settings.svelte.ts   server settings cache + per-device UI prefs (sidebar, density, refresh override)
      theme.svelte.ts      light | dark | system (follows the OS live)
      toast.svelte.ts      toast queue (rendered by components/app/ToastRegion with aria-live)
      live.svelte.ts       bridges the active page poller to the topbar "Updated Ns ago" indicator
    utils/
      format.ts            bytes (binary, 1 decimal), relative/absolute time, durations, CIDR helpers
      validation.ts        IPv4/IPv6/CIDR/hostname/DNS-list/port/MTU/password validators
      poll.svelte.ts       createPoller(fn, {intervalMs}) — pauses when hidden, single in-flight, refresh on focus
      keyboard.ts          Ctrl/Cmd+K palette, ?, /, g+d/i/p/a/s chords
      dom.ts               uid, clickOutside action, copyText, focus helpers
      icons.ts             IconComponent type for lucide icons passed as props
    components/
      ui/                  Button, IconButton, Input, Textarea, Select, Switch, Checkbox, Badge, Card, Dialog,
                           Drawer, ConfirmDialog, Tabs, Table (sortable, sticky header, selection, card mode
                           <768px), Pagination, EmptyState, ErrorState, Skeleton, Tooltip, DropdownMenu,
                           CopyButton, CodeBlock, Kbd, Spinner, ProgressRing, Alert, Stat, SegmentedControl,
                           DateTimePicker
      charts/              AreaChart (SVG, Download/Upload, crosshair + keyboard, legend, table view), Sparkline
      app/                 AppShell, Sidebar (rail + mobile sheet), Topbar, CommandPalette, HelpDialog,
                           LiveIndicator, ToastRegion, PageHeader, Logo, StatusDot, PeerStatusBadge,
                           InterfaceStatusBadge
      peers/               PeerManager (table + drawer + forms + confirmations + bulk bar), PeerTable, PeerRow,
                           PeerDrawer, PeerForm, PeerOnboardModal, ShareLinkPanel/Modal, PeerActionsMenu,
                           BulkActionBar
      interfaces/          InterfaceCard, InterfaceForm (3-step wizard), InterfaceSettingsPanel
      security/            PasswordChangeForm, MfaCard, MfaSetupDialog, RecoveryCodes, SessionsList,
                           ApiKeysPanel, UsersPanel
  routes/
    +layout.svelte         boots auth (one /auth/refresh), route guards, AppShell vs bare layout
    +page.svelte           Dashboard
    login/, setup/         public auth pages (MFA step, 3-step first-run wizard)
    interfaces/            list (+ ?new=1 wizard) and [name]/ detail (peers, settings, activity tabs)
    peers/                 global peer search
    audit/                 audit log with filters, pagination, CSV export
    settings/              ?tab= general | security | api-keys | users | data | appearance | about
    share/[token]/         public one-time config page (no shell)
    +error.svelte
```

## Conventions

- Svelte 5 runes only (`$state`, `$derived`, `$effect`, `$props`, `$bindable`, snippets). No `svelte/store`.
- Dialogs, drawers, the palette and the mobile sidebar use the native `<dialog>` element for focus trapping,
  Escape handling and focus restoration.
- Colors come from tokens in `app.css` (`bg-surface`, `text-fg-muted`, `border-border`, …); never hard-code hex
  in components. Chart series colors are `--chart-download` / `--chart-upload`, validated for both themes.
- Every list has loading (skeleton), empty (with a primary action) and error (retry) states; every mutation
  gives feedback via toast or inline error and updates the UI in place.
- Destructive actions go through `ConfirmDialog`; deleting an interface requires typing its name.
- The access token lives only in memory (`lib/api/client.ts`). Nothing sensitive is written to localStorage.
