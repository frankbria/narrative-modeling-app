import { publicEnvScript } from '@/lib/runtimeEnv'

/** Rendered in <head> by the root layout so the settings exist before any bundle reads them. */
export function PublicEnvScript() {
  return <script dangerouslySetInnerHTML={{ __html: publicEnvScript() }} />
}
