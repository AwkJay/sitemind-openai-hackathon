# SiteMind — Frontend (Command Center)

The polished "Blueprint Intelligence" ops console for SiteMind: AI code-compliance,
a cited project copilot, predictive schedule risk and a knowledge graph for a
hyperscale data-centre megaproject.

**Stack:** Next.js 14 (App Router) · TypeScript · Tailwind · Recharts · Lucide.
Dark ops-console theme only (Graphite base + Hi-Vis Lime signal). Fonts via
`next/font/google`: Space Grotesk (display) · Inter (body) · JetBrains Mono (data/citations).

## Run

```bash
cd frontend
npm install
npm run dev          # http://localhost:3000
```

Optional — point at a live backend (defaults to `http://localhost:8000`):

```bash
cp .env.example .env.local   # edit NEXT_PUBLIC_API_URL if needed
```

> **Resilient by design:** every API call gracefully falls back to bundled mock
> data (`lib/mocks.ts`) if the backend is unreachable, so the full demo path —
> including the streaming compliance reasoning — always renders with no backend.

## Build / checks

```bash
npm run build        # production build + typecheck
npm run lint         # next lint
```

## Pages

| Route         | Purpose                                                                 |
| ------------- | ----------------------------------------------------------------------- |
| `/`           | Overview — animated ROI ticker + summary cards (NCRs, schedule, RFIs).  |
| `/compliance` | **Hero.** Document list → streaming reasoning panel → cited NCR cards.  |
| `/copilot`    | Chat with inline `[n]` citations + "seen-before RFI" callout.           |
| `/schedule`   | Recharts gantt (critical path / at-risk) + top risk list with lead-time.|
| `/graph`      | SVG knowledge graph: equipment → spec → standard → RFI.                  |

## Where the design system lives

- `app/globals.css` — CSS variables (palette), blueprint grid, fonts, scanline.
- `tailwind.config.ts` — tokens wired to Tailwind colours/fonts/animations.
- `components/CitedClauseBox.tsx` — the signature "VERIFIED · STANDARD" clause box.
- `components/NCRCard.tsx`, `components/CountUp.tsx`, `components/Shell.tsx`.
- `lib/types.ts` mirrors `backend/app/schemas.py`; `lib/api.ts` is the client;
  `lib/mocks.ts` holds the demo data (real IS clause text).
