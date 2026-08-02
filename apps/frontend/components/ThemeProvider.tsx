'use client'

import { ThemeProvider as NextThemesProvider } from 'next-themes'

/**
 * Makes the `.dark` class reachable (#407).
 *
 * `app/globals.css` has carried a full `.dark` token block and `@custom-variant dark
 * (&:is(.dark *))` since #345, and 27 `dark:` utilities are written across the app —
 * but nothing ever put `.dark` on the document, so every one of them was dead code.
 * That is also why #398's dark-mode acceptance criterion was unanswerable.
 *
 * `attribute="class"` is what matches the custom variant; anything else (the
 * `data-theme` default) would leave the same tokens unreachable in a new way.
 */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      // Transitions on a theme swap animate every colour on the page at once,
      // which reads as a flash rather than a fade.
      disableTransitionOnChange
    >
      {children}
    </NextThemesProvider>
  )
}
