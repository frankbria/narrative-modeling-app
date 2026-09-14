/**
 * #528 AC4 — every `page.tsx` route under `app/` must be reachable from navigation.
 *
 * The bug this guards: `app/settings/billing/page.tsx` — the page with the
 * "Upgrade to Pro" button — had **zero inbound links** anywhere in the app, so the
 * checkout entry point could not be reached by navigation. A brand-new page that
 * nobody links to is invisible to every render test (it renders fine in isolation),
 * so only a source-level reachability check catches it.
 *
 * Model (deliberately the same shape as the backend's
 * `tests/test_api/test_every_router_is_mounted.py`): a page route passes if it is
 * **referenced** by navigation, is a documented framework root, or is on an
 * explicit allowlist with a reason. Navigation reaches a route three ways:
 *
 *   1. A route literal after `href` / `router.push|replace` / `redirect(` / `route:`
 *      — plain (`'/upload'`) or template (`` `/datasets/${id}/prepare` ``).
 *   2. The workflow-stage config (`lib/types/workflow.ts` `route:` entries), driven
 *      by `WorkflowBar` / dashboard / quickstart through `buildStageUrl`, which for
 *      the dataset-scoped stages appends `/${datasetId}` (so a stage route `R` can
 *      produce both `R` and `R/:seg`).
 *   3. Framework roots that take no inbound app link: `/` (landing) and everything
 *      under `/auth/` (NextAuth `pages:` targets in `auth.ts`, reached by provider
 *      redirects).
 *
 * Known limitation (shared with the backend mount test): this is a "referenced at
 * least once" check, not a full reachability walk — a page linked *only* from
 * another orphan counts as referenced. That is fine for the failure mode here
 * (a page with no inbound links at all); tightening to a graph walk is a follow-up
 * if a transitive orphan ever bites.
 */
import fs from 'fs';
import path from 'path';

const FRONTEND = path.resolve(__dirname, '..', '..');
const APP = path.join(FRONTEND, 'app');
const NAV_SOURCE_DIRS = ['app', 'components', 'lib'].map((d) => path.join(FRONTEND, d));

/** Collapse dynamic segments (`[id]`, `${expr}`) to one placeholder so a page route
 *  and the link that reaches it compare equal. */
function normalizeRoute(route: string): string {
  const cleaned = route.split(/[?#]/)[0]; // drop query / hash
  const norm = cleaned
    .replace(/\$\{[^}]*\}/g, ':seg') // template interpolation
    .replace(/\[[^\]]*\]/g, ':seg') // Next dynamic segment
    .replace(/\/+/g, '/')
    .replace(/\/$/, ''); // strip trailing slash
  return norm === '' ? '/' : norm;
}

/** Every `page.tsx` under `app/`, as a normalized route. The `app/api` subtree is
 *  excluded — those are HTTP handlers (`route.ts`), not navigable pages. */
function collectPageRoutes(dir: string, rel = ''): string[] {
  const out: string[] = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      if (rel === '' && entry.name === 'api') continue; // skip app/api
      out.push(...collectPageRoutes(path.join(dir, entry.name), `${rel}/${entry.name}`));
    } else if (entry.name === 'page.tsx') {
      out.push(normalizeRoute(rel === '' ? '/' : rel));
    }
  }
  return out;
}

function walkFiles(dir: string): string[] {
  const out: string[] = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === 'node_modules' || entry.name === '.next') continue;
      out.push(...walkFiles(full));
    } else if (/\.(t|j)sx?$/.test(entry.name)) {
      out.push(full);
    }
  }
  return out;
}

/** Route literals referenced with navigation intent: the first quoted/backtick
 *  argument after `href` / `push` / `replace` / `redirect` / `route` that begins
 *  with `/`. Intent-scoped so an unrelated `/`-string (an API path, a regex) does
 *  not falsely mark a page reachable. */
function collectNavigableLiterals(src: string): string[] {
  const out: string[] = [];
  const re = /(?:href|push|replace|redirect|route)\s*[=:(]\s*\{?\s*[`'"](\/[^`'"]*)[`'"]/g;
  for (const m of src.matchAll(re)) out.push(normalizeRoute(m[1]));
  return out;
}

/** Workflow-stage routes from `lib/types/workflow.ts`. Every stage route `R` is
 *  navigable; the dataset-scoped stages are also reached as `R/:seg` because
 *  dashboard's `handleNavigateToStage` and `buildStageUrl` append `/${datasetId}`
 *  for every stage except `/upload` (which it guards explicitly), so `/upload/:seg`
 *  — a variant no navigation produces — is deliberately NOT registered. */
function collectWorkflowStageRoutes(): string[] {
  const src = fs.readFileSync(path.join(FRONTEND, 'lib', 'types', 'workflow.ts'), 'utf8');
  const out: string[] = [];
  for (const m of src.matchAll(/route:\s*['"](\/[^'"]*)['"]/g)) {
    const r = normalizeRoute(m[1]);
    out.push(r);
    if (r !== '/upload') out.push(normalizeRoute(`${r}/:seg`));
  }
  return out;
}

/** The NextAuth pages, read from `auth.ts`'s `pages:` config — the only routes
 *  reached purely by provider redirect with no inbound app link. Derived from the
 *  config (like the workflow routes) rather than a `/auth/` prefix match, so a NEW
 *  page added under `app/auth/` is NOT auto-exempted: it must be linked or
 *  allowlisted, the same guarantee the guard gives every other route. */
function collectAuthPages(): string[] {
  const src = fs.readFileSync(path.join(FRONTEND, 'auth.ts'), 'utf8');
  const out: string[] = [];
  for (const m of src.matchAll(
    /(?:signIn|signOut|verifyRequest|newUser|error)\s*:\s*['"](\/[^'"]*)['"]/g,
  )) {
    out.push(normalizeRoute(m[1]));
  }
  return out;
}

const FRAMEWORK_ROOTS = new Set<string>(['/', ...collectAuthPages()]);

/** Routes that legitimately take no inbound app link: the landing page and the
 *  NextAuth pages (reached by provider redirect). */
function isFrameworkRoot(route: string): boolean {
  return FRAMEWORK_ROOTS.has(route);
}

/**
 * Pages known to be orphaned today, kept passing so the guard protects against NEW
 * orphans while these are resolved separately. Each entry MUST stay a real, still
 * non-navigable page or the anti-stale check below fails and tells you to drop it.
 * Tracked by #738 (link-into-nav or delete the legacy dataset-scoped flow).
 */
const KNOWN_ORPHANS: Record<string, string> = {
  '/recipes': 'Full recipes UI with no inbound link; nav home is a product decision (#738)',
  '/datasets/:seg/engineer':
    'Legacy dataset-scoped feature-engineering page, superseded by the /features workflow stage; nothing links in (#738)',
};

describe('#528 AC4 — page routes are reachable from navigation', () => {
  const pageRoutes = [...new Set(collectPageRoutes(APP))].sort();
  const navigable = new Set<string>([
    ...NAV_SOURCE_DIRS.flatMap((d) =>
      walkFiles(d).flatMap((f) => collectNavigableLiterals(fs.readFileSync(f, 'utf8'))),
    ),
    ...collectWorkflowStageRoutes(),
  ]);

  const reachable = (route: string) =>
    navigable.has(route) || isFrameworkRoot(route) || route in KNOWN_ORPHANS;

  it('finds a non-trivial set of pages (the walker works)', () => {
    expect(pageRoutes.length).toBeGreaterThan(20);
    expect(pageRoutes).toContain('/settings/billing'); // the #528 page
  });

  it('every page route is reachable, a framework root, or an allowlisted orphan', () => {
    const orphans = pageRoutes.filter((r) => !reachable(r));
    expect(orphans).toEqual([]);
  });

  it('the KNOWN_ORPHANS allowlist has no stale entries', () => {
    const pages = new Set(pageRoutes);
    for (const route of Object.keys(KNOWN_ORPHANS)) {
      // still a real page
      expect(pages.has(route)).toBe(true);
      // still genuinely unreachable — otherwise it must leave the allowlist
      expect(navigable.has(route) || isFrameworkRoot(route)).toBe(false);
    }
  });
});
