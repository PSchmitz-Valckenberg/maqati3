# Maqati3 Frontend

The web interface for Maqati3, an archive and search platform for recorded fatawa. Built with Next.js (App Router), React 19, Tailwind CSS, and `next-intl` supporting English, Arabic (RTL), and German.

## Getting Started

Install dependencies and start the local development server:

```bash
cd frontend
npm ci
npm run dev
```

The frontend will be available at [http://localhost:3000](http://localhost:3000).

### Backend Proxy Configuration

In development, Next.js proxies API requests to the backend:

- Configure `API_ORIGIN` in your environment (defaults to `http://localhost:8000`).
- **Dev proxy payload limit:** The local development proxy enforces a **10 MB payload limit** on request bodies (e.g. file uploads). For larger uploads in development or production setups, see [docs/BETRIEB.md](../docs/BETRIEB.md) (or [docs/BETRIEB.en.md](../docs/BETRIEB.en.md)).

## Project Structure & Localization

- **Pages and Routes:** `src/app/[locale]/` — localized routes using the App Router.
- **Translations:** `messages/{en,ar,de}.json` — interface strings managed with `next-intl`.
- **Public Assets:** `public/` — static assets served at the root.

## Verification & Testing

Run code quality checks and tests before submitting changes:

```bash
# Lint code
npm run lint

# Type check
npx tsc --noEmit

# Run unit tests
npm test
```
