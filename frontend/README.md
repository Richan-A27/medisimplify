# MediSimplify frontend

Next.js 16 (App Router), TypeScript and Tailwind CSS. See the [root README](../README.md) for setup.

```bash
npm install
npm run dev        # http://localhost:3000
npm run lint
npm run typecheck
npm run build
npm run e2e        # Playwright; needs `npx playwright install chromium` once
```

Requires Node.js >= 20.9. The backend URL defaults to `http://localhost:8000`. Override it with `NEXT_PUBLIC_API_BASE_URL` in `.env.local` (see `.env.example`).
