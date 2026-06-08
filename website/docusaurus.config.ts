import { themes as prismThemes } from 'prism-react-renderer';
import type { Config } from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
  title: 'CFA — Contextual Flux Architecture',
  tagline: 'Governed execution for AI agents and data systems.',
  favicon: 'img/favicon.ico',

  future: { v4: true },

  url: 'https://marquesantero.github.io',
  baseUrl: '/cfa/',
  trailingSlash: false,

  organizationName: 'marquesantero',
  projectName: 'cfa',

  onBrokenLinks: 'warn',

  i18n: {
    defaultLocale: 'en',
    locales: ['en', 'pt-BR'],
    localeConfigs: {
      en: { htmlLang: 'en-US', label: 'English' },
      'pt-BR': { htmlLang: 'pt-BR', label: 'Português' },
    },
  },

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          editUrl: 'https://github.com/marquesantero/cfa/tree/main/website/',
          routeBasePath: 'docs',
        },
        blog: {
          showReadingTime: true,
          feedOptions: { type: ['rss', 'atom'], xslt: true },
          editUrl: 'https://github.com/marquesantero/cfa/tree/main/website/',
          onInlineTags: 'warn',
          onInlineAuthors: 'warn',
          onUntruncatedBlogPosts: 'warn',
        },
        theme: { customCss: './src/css/custom.css' },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    image: 'img/cfa-social-card.png',
    colorMode: { respectPrefersColorScheme: true },
    announcementBar: {
      id: 'cfa-1-1-0',
      content:
        '<strong>CFA 1.1.0</strong> — pre-execution governance with structured remediation, ' +
        'offline-verifiable SHA-256 audit, and sub-3 ms p99 · ' +
        '<a target="_blank" rel="noopener" href="https://github.com/marquesantero/cfa/blob/main/CHANGELOG.md">changelog</a>',
      backgroundColor: '#0d1525',
      textColor: '#3dffa0',
      isCloseable: false,
    },
    navbar: {
      title: 'CFA',
      logo: { alt: 'CFA', src: 'img/logo.svg' },
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'docsSidebar',
          position: 'left',
          label: 'Docs',
        },
        { to: '/blog', label: 'Blog', position: 'left' },
        {
          type: 'localeDropdown',
          position: 'right',
        },
        {
          href: 'https://github.com/marquesantero/cfa',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Docs',
          items: [
            { label: 'Whitepaper', to: '/docs/whitepaper' },
            { label: 'Getting Started', to: '/docs/getting-started' },
            { label: 'FAQ', to: '/docs/faq' },
          ],
        },
        {
          title: 'Community',
          items: [
            { label: 'GitHub Issues', href: 'https://github.com/marquesantero/cfa/issues' },
            { label: 'GitHub Discussions', href: 'https://github.com/marquesantero/cfa/discussions' },
          ],
        },
        {
          title: 'More',
          items: [
            { label: 'Blog', to: '/blog' },
            { label: 'GitHub', href: 'https://github.com/marquesantero/cfa' },
            { label: 'PyPI', href: 'https://pypi.org/project/cfa-kernel/' },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} Antero Marques. Built with Docusaurus.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
      additionalLanguages: ['python', 'yaml', 'bash', 'json'],
    },
  } satisfies Preset.ThemeConfig,

  customFields: {
    version: '1.1.0',
    latestStable: '1.1.0',
  },
};

export default config;
