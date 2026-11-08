// Sentry 11 exports the build wrapper from `/config`; the package root no longer has it.
import { withSentryConfig } from '@sentry/nextjs/config';

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Enable standalone output for Docker production builds
  output: process.env.NODE_ENV === 'production' ? 'standalone' : undefined,

  // Strip console.* from production bundles so debug logging (and any data it
  // stringifies) never ships to the browser. console.error/warn are kept for
  // real diagnostics. (issue #288)
  compiler: {
    removeConsole:
      process.env.NODE_ENV === 'production'
        ? { exclude: ['error', 'warn'] }
        : false,
  },

  // Security headers
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          {
            key: 'X-Frame-Options',
            value: 'DENY',
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
          {
            key: 'Referrer-Policy',
            value: 'strict-origin-when-cross-origin',
          },
        ],
      },
    ];
  },
};

// Browser source maps go to Sentry and are then deleted, so stack traces read as source
// and no `.map` is served (#1158). Without a token nothing is generated: a map with
// nowhere to go could only end up public. The Dockerfile deletes any `.map` left over.
export default withSentryConfig(nextConfig, {
  org: process.env.SENTRY_ORG,
  project: process.env.SENTRY_PROJECT,
  authToken: process.env.SENTRY_AUTH_TOKEN,
  release: { name: process.env.SENTRY_RELEASE || undefined },
  sourcemaps: {
    disable: !process.env.SENTRY_AUTH_TOKEN,
    deleteSourcemapsAfterUpload: true,
  },
  silent: !process.env.SENTRY_AUTH_TOKEN,
  telemetry: false,
});
