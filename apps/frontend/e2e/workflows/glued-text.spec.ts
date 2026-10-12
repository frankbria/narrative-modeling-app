import { readdirSync } from 'fs';
import { join } from 'path';
import type { APIRequestContext } from '@playwright/test';
import { test, expect } from '../fixtures';
import { gluedBoundaries } from '../helpers/gluedText';

/**
 * No server-rendered page glues an interpolation to the prose after it (#473, #603).
 *
 * The defect is invisible to component tests (jsdom renders the space the server
 * drops) and was first found by eye on the Terms page. This reads the HTML the server
 * actually sends for every route that needs no id, with the test user's session.
 */
const APP_DIR = join(__dirname, '../../app');
/** The pages customers read closely. The smoke gate reads these on every run. */
const READ_CLOSELY = ['/legal/terms', '/legal/privacy', '/pricing'];

/** Routes with no dynamic segment: `app/legal/terms/page.tsx` is `/legal/terms`. */
function staticRoutes(dir = APP_DIR, route = ''): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    if (entry.isFile()) return entry.name === 'page.tsx' ? [route || '/'] : [];
    if (entry.name.startsWith('[') || entry.name === 'api') return [];
    // A route group, `(name)`, is a folder that adds nothing to the URL.
    const segment = entry.name.startsWith('(') ? '' : `/${entry.name}`;
    return staticRoutes(join(dir, entry.name), route + segment);
  });
}

/** The server's HTML for each route: which were served, and every glued boundary found. */
async function read(request: APIRequestContext, routes: string[]) {
  const served: string[] = [];
  const glued: string[] = [];
  for (const route of routes) {
    // A generous timeout: the dev server compiles a route the first time it is asked for.
    const response = await request.get(route, { headers: { Accept: 'text/html' }, timeout: 60_000 });
    // /admin is a 404 for this user, and a route may redirect to one that needs an id.
    if (response.status() !== 200) continue;
    served.push(route);
    glued.push(...gluedBoundaries(await response.text()).map((text) => `${route}: …${text}…`));
  }
  return { served, glued };
}

test.describe('glued text in the server render (#603)', () => {
  test('the detector names the text around a glued boundary @smoke', () => {
    const glued = '<p>Welcome to <!-- -->Narrative Modeling App<!-- -->service, version <!-- -->2.</p>';

    expect(gluedBoundaries(glued)).toEqual([expect.stringContaining('Narrative Modeling App|service')]);
    expect(gluedBoundaries('<p>Narrative Modeling App<!-- --> <!-- -->service</p>')).toEqual([]);
  });

  test('the legal and pricing pages join no interpolation to the prose after it @smoke', async ({
    authenticatedPage,
  }) => {
    test.setTimeout(120_000);

    const { served, glued } = await read(authenticatedPage.request, READ_CLOSELY);

    expect(served, 'a page that must be read was not served').toEqual(READ_CLOSELY);
    expect(glued, 'write {" "} after the interpolation').toEqual([]);
  });

  // Not in the smoke gate: the dev server compiles each of ~30 routes on first request.
  test('nor does any other route that needs no id', async ({ authenticatedPage }) => {
    test.setTimeout(300_000);

    const { served, glued } = await read(authenticatedPage.request, staticRoutes());

    expect(served.length, 'most routes should be served to a signed-in user').toBeGreaterThan(15);
    expect(glued, 'write {" "} after the interpolation').toEqual([]);
  });
});
