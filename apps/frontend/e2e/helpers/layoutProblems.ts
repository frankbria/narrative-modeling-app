import type { Page } from '@playwright/test';

/**
 * What is visibly wrong with the text inside one card (#809): text cut off by its
 * box, text sticking out of the card, and two pieces of text drawn over each other.
 * Measured in the browser, so it sees what a component test cannot: jsdom lays
 * nothing out. Returns one line per problem; empty means the card reads cleanly.
 */
export async function textLayoutProblems(page: Page, cardHeading: string): Promise<string[]> {
  // The Card (components/ui/card.tsx carries `bg-card`) around the heading.
  const card = page
    .getByRole('heading', { name: cardHeading })
    .locator('xpath=ancestor::div[contains(concat(" ", normalize-space(@class), " "), " bg-card ")][1]');
  return card.evaluate((card) => {
    const box = card.getBoundingClientRect();
    const label = (el: Element) => `"${(el.textContent || '').trim().slice(0, 40)}"`;
    const ownText = (el: Element) =>
      Array.from(el.childNodes).some((n) => n.nodeType === Node.TEXT_NODE && (n.textContent || '').trim() !== '');
    const texts = Array.from(card.querySelectorAll('*')).filter(
      (el) => ownText(el) && el.getClientRects().length > 0 && !el.closest('.sr-only'),
    );

    const problems: string[] = [];
    for (const el of texts) {
      const r = el.getBoundingClientRect();
      if (el.scrollWidth > el.clientWidth + 1) problems.push(`cut off: ${label(el)}`);
      if (r.left < box.left - 1 || r.right > box.right + 1) problems.push(`outside the card: ${label(el)}`);
    }
    for (let i = 0; i < texts.length; i++) {
      for (let j = i + 1; j < texts.length; j++) {
        if (texts[i].contains(texts[j]) || texts[j].contains(texts[i])) continue;
        const a = texts[i].getBoundingClientRect();
        const b = texts[j].getBoundingClientRect();
        const overlapX = Math.min(a.right, b.right) - Math.max(a.left, b.left);
        const overlapY = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
        if (overlapX > 1 && overlapY > 1) problems.push(`drawn over each other: ${label(texts[i])} and ${label(texts[j])}`);
      }
    }
    return problems;
  });
}
