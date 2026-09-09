/**
 * Shell for the public legal pages (issue #473).
 *
 * These are the only pages an anonymous visitor can reach, so they carry their
 * own width and prose styling rather than relying on the app chrome — the root
 * layout renders signed-out content in a centring flex column with no sidebar.
 */
export default function LegalLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="w-full max-w-3xl mx-auto px-6 pt-10 pb-20 text-foreground">
      <article className="prose prose-slate dark:prose-invert max-w-none prose-headings:scroll-mt-6">
        {children}
      </article>
    </div>
  )
}
