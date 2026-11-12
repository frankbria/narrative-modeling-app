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
 * The settings the server wrote onto this page's `<html>` element. That element is
 * parsed before any script can run, so a module reading a setting as it loads finds
 * it whatever order the bundles arrive in.
 */
function pageSettings(): PublicEnv {
  window.__PUBLIC_ENV__ ??= JSON.parse(document.documentElement.dataset.publicEnv ?? '{}') as PublicEnv
  return window.__PUBLIC_ENV__
}

/**
 * A public setting of this deployment, read when the code runs: one image serves
 * every host (#831). Blank counts as unset, because compose passes a blank.
 */
export function publicEnv(name: PublicEnvName): string | undefined {
  // A browser reads only what the server rendered into the page: its own `process.env` holds
  // whatever `next build` saw. The server reads by bracket, which `next build` does not inline.
  const settings = typeof window === 'undefined' ? process.env : pageSettings()
  return settings[name] || undefined
}

/** The public settings this server holds, as the root layout writes them onto `<html data-public-env>`. */
export function publicEnvJson(env: Readonly<Record<string, string | undefined>> = process.env): string {
  const settings: PublicEnv = {}
  for (const name of PUBLIC_ENV_NAMES) {
    const value = env[name]
    if (value) settings[name] = value
  }
  return JSON.stringify(settings)
}
