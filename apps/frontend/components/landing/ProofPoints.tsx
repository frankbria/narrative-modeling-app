/** Positioning.md section 4: the three proof points, copy word for word. */
const PROOF_POINTS = [
  {
    title: 'Validated, not vibes',
    copy: 'About ten algorithms, cross-validated, with an explanation of why the winner won.',
  },
  {
    title: 'Explained and reproducible',
    copy: 'SHAP explanations for every model, a full version history, and a self-contained Python or Docker export you own.',
  },
  {
    title: 'Safe with real data',
    copy: 'PII is scanned and masked before anything reaches a language model; every AI feature works without an AI key; one-click erasure; Apache 2.0 source you can read and self-host.',
  },
]

export function ProofPoints() {
  const points = PROOF_POINTS
  return (
    <section aria-labelledby="proof-heading" className="space-y-4">
      <h2 id="proof-heading" className="text-2xl font-semibold text-foreground">
        Why it holds up
      </h2>
      <div className="grid gap-4 md:grid-cols-3">
        {points.map((point) => (
          <div key={point.title} className="rounded-lg border border-border bg-card p-5 text-card-foreground shadow-sm">
            <h3 className="font-semibold">{point.title}</h3>
            <p className="mt-2 text-sm text-muted-foreground">{point.copy}</p>
          </div>
        ))}
      </div>
    </section>
  )
}
