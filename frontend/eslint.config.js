import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  // dist: build output; coverage: generated reports; components/ui: auto-generated shadcn files
  globalIgnores(['dist', 'coverage/**', 'src/components/ui/**']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
    },
    rules: {
      // TanStack Router route files export `Route = createFileRoute(...)(...)` alongside
      // a component function — this is the intended pattern, not a HMR issue.
      // Register TanStack Router HOC creators so react-refresh does not false-positive.
      'react-refresh/only-export-components': [
        'warn',
        {
          allowConstantExport: true,
          extraHOCs: ['createFileRoute', 'createRootRouteWithContext'],
        },
      ],
    },
  },
])
