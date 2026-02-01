import { defineConfig } from 'vitepress'

export default defineConfig({
    title: "TunnBox",
    description: "Modern WireGuard VPN Manager",
    head: [
        ['link', { rel: 'icon', href: '/logo.svg' }]
    ],
    themeConfig: {
        logo: '/logo.svg',
        nav: [
            { text: 'Home', link: '/' },
            { text: 'Guide', link: '/getting-started/installation' },
            { text: 'API', link: '/api/endpoints' }
        ],

        sidebar: [
            {
                text: 'Getting Started',
                items: [
                    { text: 'Installation', link: '/getting-started/installation' },
                    { text: 'Configuration', link: '/getting-started/configuration' },
                    { text: 'First Setup', link: '/getting-started/first-setup' }
                ]
            },
            {
                text: 'Guides',
                items: [
                    { text: 'Architecture', link: '/guides/architecture' },
                    { text: 'Interface Management', link: '/guides/interface-management' },
                    { text: 'Peer Management', link: '/guides/peer-management' },
                    { text: 'Security', link: '/guides/security' },
                    { text: 'Backup & Restore', link: '/guides/backup-restore' },
                    { text: 'Updating', link: '/guides/updating' },
                    { text: 'Troubleshooting', link: '/guides/troubleshooting' },
                    { text: 'FAQ', link: '/guides/faq' }
                ]
            },
            {
                text: 'Deployment',
                items: [
                    { text: 'Production', link: '/deployment/production' }
                ]
            },
            {
                text: 'API Reference',
                items: [
                    { text: 'Endpoints', link: '/api/endpoints' }
                ]
            }
        ],

        socialLinks: [
            { icon: 'github', link: 'https://github.com/pgorbunov/tunnbox' }
        ],

        footer: {
            message: 'Released under the MIT License.',
            copyright: 'Copyright © 2026 TunnBox'
        }
    }
})
