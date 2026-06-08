import type { SidebarsConfig } from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  docsSidebar: [
    'intro',
    'compare',
    {
      type: 'category',
      label: 'Core',
      items: ['getting-started', 'guide', 'whitepaper'],
    },
    {
      type: 'category',
      label: 'Reference',
      items: ['cli', 'policy-bundles', 'mcp-server', 'backends', 'behavior-spec', 'reporting', 'api'],
    },
    {
      type: 'category',
      label: 'Integrations',
      items: ['integrations/use-cfa-guard-with-frameworks'],
    },
    'extending',
    'faq',
    'architecture-notes',
  ],
};

export default sidebars;
