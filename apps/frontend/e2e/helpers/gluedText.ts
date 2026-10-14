/**
 * Text glued together in server-rendered HTML (#473, #603).
 *
 * React separates adjacent text nodes in its server output with `<!-- -->`. When an
 * interpolation meets prose with no space between them, the served page reads
 * "SheetPredictservice" while jsdom, and so every component test, renders
 * the space. The signature is that marker with a word character on both sides.
 */
const GLUED = /[A-Za-z0-9.,)]<!-- -->[A-Za-z0-9(]/g;

/** Each glued boundary in `html`, as the text around it with the join shown as `|`. */
export function gluedBoundaries(html: string): string[] {
  return [...html.matchAll(GLUED)].map((match) => {
    const at = match.index ?? 0;
    const around = html.slice(Math.max(0, at - 40), at + match[0].length + 40);
    return around.replace(/<!-- -->/g, '|').replace(/\s+/g, ' ');
  });
}
