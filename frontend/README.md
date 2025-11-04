# Frontend for WireGuard Obfuscator Easy API

React + TypeScript frontend with i18n support.

## Development

```bash
# Install dependencies
npm install

# Start development server
npm run dev
```

The dev server will proxy API requests to `http://localhost:5000`.

## Building for Production

```bash
# Build the frontend
npm run build
```

This will build the frontend and output files to `../static/` directory, which Flask will serve.

## Adding New Languages

1. Create a new JSON file in `src/i18n/locales/` (e.g., `de.json`)
2. Copy the structure from `en.json` and translate the values
3. Import and add to `src/i18n/index.ts`:

```typescript
import de from './locales/de.json';

i18n.init({
  resources: {
    en: { translation: en },
    ru: { translation: ru },
    de: { translation: de }, // Add here
  },
  // ...
});
```

4. Add language option to `src/components/LanguageSelector.tsx`

