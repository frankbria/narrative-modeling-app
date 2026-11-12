/**
 * The root layout hands the browser this deployment's public settings as they are
 * when the page is rendered, ahead of every bundle (#831).
 */
import { readFileSync } from 'fs'
import { join } from 'path'
import { renderToStaticMarkup } from 'react-dom/server'
import { PublicEnvScript } from '@/components/PublicEnvScript'

const ORIGINAL_API_URL = process.env.NEXT_PUBLIC_API_URL

afterEach(() => {
  delete window.__PUBLIC_ENV__
  process.env.NEXT_PUBLIC_API_URL = ORIGINAL_API_URL
})

function renderedScriptText(): string {
  const holder = document.createElement('div')
  holder.innerHTML = renderToStaticMarkup(<PublicEnvScript />)
  const scripts = holder.querySelectorAll('script')
  expect(scripts).toHaveLength(1)
  return scripts[0].textContent ?? ''
}

describe('PublicEnvScript', () => {
  it('carries the API URL the environment holds at render time, not at import time', () => {
    process.env.NEXT_PUBLIC_API_URL = 'https://dev.example/api/v1'
    new Function(renderedScriptText())()
    expect(window.__PUBLIC_ENV__?.NEXT_PUBLIC_API_URL).toBe('https://dev.example/api/v1')

    process.env.NEXT_PUBLIC_API_URL = 'https://www.example/api/v1'
    new Function(renderedScriptText())()
    expect(window.__PUBLIC_ENV__?.NEXT_PUBLIC_API_URL).toBe('https://www.example/api/v1')
  })

  it('is mounted by the root layout in <head>, so it runs before any bundle', () => {
    const layout = readFileSync(join(__dirname, '..', '..', 'app', 'layout.tsx'), 'utf8')

    expect(layout).toMatch(/<head>\s*<PublicEnvScript \/>\s*<\/head>\s*<body/)
  })
})
