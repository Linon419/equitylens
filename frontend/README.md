# EquityLens Web

The EquityLens web application is built with Next.js 16, React 19, TypeScript,
and Tailwind CSS. It provides English and Simplified Chinese routes with browser
language detection and a persistent language selector.

## Development

```bash
corepack pnpm install --frozen-lockfile
corepack pnpm dev
```

Open `http://localhost:3000`.

## Quality checks

```bash
corepack pnpm test
corepack pnpm lint
corepack pnpm build
```

Project-wide setup and architecture are documented in the root
[`README.md`](../README.md). Production settings are documented in the
[Vercel deployment guide](../deploy/vercel/README.md).
