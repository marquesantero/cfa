import type { SidebarsConfig } from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  docsSidebar: [
    'intro',
    {
      type: 'category',
      label: 'Core',
      items: ['whitepaper', 'getting-started', 'guide'],
    },
    {
      type: 'category',
      label: 'Reference',
      items: ['cli', 'policy-bundles', 'mcp-server', 'backends', 'behavior-spec', 'reporting', 'api'],
    },
    {
      type: 'category',
      label: 'Integrations',
      items: ['integrations/langgraph', 'integrations/openai-agents'],
    },
    'faq',
    'architecture-notes',
  ],
};

export default sidebars;
