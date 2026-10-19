/**
 * @jest-environment node
 *
 * The public URL and the production switch are read when a request arrives, not
 * when the image is built (#766, #831): one image serves dev. and www., so
 * neither can be a build-time constant.
 */
import { isProduction, siteMetadata, siteUrl } from '@/lib/site'
import { COMPANY } from '@/lib/legal/company'

describe('siteUrl', () => {
  it('is the NEXTAUTH_URL of this deployment, read from the env it is given', () => {
    expect(siteUrl({ NEXTAUTH_URL: 'https://dev.sheetpredict.app' }).href).toBe('https://dev.sheetpredict.app/')
    expect(siteUrl({ NEXTAUTH_URL: 'https://www.sheetpredict.app' }).href).toBe('https://www.sheetpredict.app/')
  })

  it('falls back to localhost where nothing is configured (a build, a unit test)', () => {
    expect(siteUrl({}).href).toBe('http://localhost:3000/')
  })
})

describe('isProduction', () => {
  it('is true only for the exact value "production"', () => {
    expect(isProduction({ ENVIRONMENT: 'production' })).toBe(true)
  })

  it.each([undefined, '', 'staging', 'development', 'Production'])('is false for %p (fails closed)', (value) => {
    expect(isProduction({ ENVIRONMENT: value })).toBe(false)
  })

  it('ignores NODE_ENV, which is "production" on staging too', () => {
    expect(isProduction({ NODE_ENV: 'production' })).toBe(false)
  })
})

describe('siteMetadata', () => {
  const meta = siteMetadata({ NEXTAUTH_URL: 'https://dev.sheetpredict.app' })

  it('resolves relative URLs against the runtime site URL', () => {
    expect(String(meta.metadataBase)).toBe('https://dev.sheetpredict.app/')
  })

  it('describes the product with the one value line', () => {
    expect(meta.description).toBe(COMPANY.valueLine)
    expect(meta.openGraph).toMatchObject({ siteName: COMPANY.serviceName, type: 'website' })
  })

  it('gives both card types an image', () => {
    expect(meta.openGraph).toMatchObject({ images: [expect.objectContaining({ url: '/og-image.png' })] })
    expect(meta.twitter).toMatchObject({ card: 'summary_large_image', images: ['/og-image.png'] })
  })
})
