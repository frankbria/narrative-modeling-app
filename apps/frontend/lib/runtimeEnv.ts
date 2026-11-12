export const PUBLIC_ENV_NAMES = [
  'NEXT_PUBLIC_API_URL',
  'NEXT_PUBLIC_SENTRY_DSN',
  'NEXT_PUBLIC_SENTRY_ENVIRONMENT',
  'NEXT_PUBLIC_INVITE_REQUEST_URL',
] as const

export type PublicEnvName = (typeof PUBLIC_ENV_NAMES)[number]

type PublicEnv = Partial<Record<PublicEnvName, string>>

declare global {
  interface Window {
    __PUBLIC_ENV__?: PublicEnv
  }
}

/**
 * A public setting of this deployment, read when the code runs: one image serves
 * every host (#831). Blank counts as unset, because compose passes a blank.
 */
export function publicEnv(name: PublicEnvName): string | undefined {
  const renderedIntoPage = typeof window === 'undefined' ? undefined : window.__PUBLIC_ENV__?.[name]
  // Bracket access: `next build` replaces a dotted read of a public variable with the value it was built with.
  return renderedIntoPage || process.env[name] || undefined
}

/** JavaScript for the root layout that hands the browser the public settings this server holds. */
export function publicEnvScript(env: Readonly<Record<string, string | undefined>> = process.env): string {
  const settings: PublicEnv = {}
  for (const name of PUBLIC_ENV_NAMES) {
    const value = env[name]
    if (value) settings[name] = value
  }
  // An unescaped `<` would let a value close the script element it is rendered into.
  return `window.__PUBLIC_ENV__=${JSON.stringify(settings).replace(/</g, '\\u003c')}`
}
