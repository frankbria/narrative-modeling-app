/**
 * Public /how-it-works page (#772 AC2): the eight stages, one screenshot each, and a
 * silent walkthrough of the churn sample. Stages come from `WORKFLOW_STAGES`, the
 * prose from the shared blurbs the landing page uses.
 */
import { existsSync, statSync } from 'fs'
import { join } from 'path'
import { render, screen, within } from '@testing-library/react'
import '@testing-library/jest-dom'
import HowItWorksPage, { metadata } from '@/app/how-it-works/page'
import { STAGE_BLURBS } from '@/components/landing/stageBlurbs'
import { COMPANY } from '@/lib/legal/company'
import { WORKFLOW_STAGES } from '@/lib/types/workflow'

const PUBLIC = join(__dirname, '../../public')
const MAX_IMAGE_BYTES = 200 * 1024
const MAX_VIDEO_BYTES = 3 * 1024 * 1024

describe('How it works page', () => {
  it('has one h1 and page metadata with a canonical address', () => {
    render(<HowItWorksPage />)
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/how it works/i)
    expect(String(metadata.title)).toContain(COMPANY.serviceName)
    expect(metadata.alternates?.canonical).toBe('/how-it-works')
  })

  it('lists every workflow stage in order, with its blurb and one screenshot', () => {
    render(<HowItWorksPage />)
    const stages = screen.getByRole('list', { name: /the eight stages/i })
    const items = within(stages).getAllByRole('listitem')
    expect(items).toHaveLength(WORKFLOW_STAGES.length)
    WORKFLOW_STAGES.forEach((stage, i) => {
      expect(within(items[i]).getByRole('heading', { name: stage.name })).toBeInTheDocument()
      expect(items[i]).toHaveTextContent(STAGE_BLURBS[stage.id])
      const shots = within(items[i]).getAllByRole('img')
      expect(shots).toHaveLength(1)
      expect(shots[0]).toHaveAttribute('alt', expect.stringContaining(stage.name))
    })
  })

  it('serves screenshots that exist under public/how-it-works and stay small', () => {
    render(<HowItWorksPage />)
    for (const shot of screen.getAllByRole('img')) {
      const src = shot.getAttribute('src') ?? ''
      expect(src).toMatch(/^\/how-it-works\//)
      const file = join(PUBLIC, src)
      expect(existsSync(file)).toBe(true)
      expect(statSync(file).size).toBeLessThan(MAX_IMAGE_BYTES)
    }
  })

  it('offers a silent walkthrough of the churn sample, and says it is silent', () => {
    const { container } = render(<HowItWorksPage />)
    const video = container.querySelector('video')!
    expect(video).not.toBeNull()
    expect(video).toHaveAttribute('controls')
    const src = video.querySelector('source')!.getAttribute('src')!
    expect(src).toMatch(/^\/how-it-works\/.+\.webm$/)
    expect(statSync(join(PUBLIC, src)).size).toBeLessThan(MAX_VIDEO_BYTES)
    expect(screen.getByText(/no audio|silent/i)).toBeInTheDocument()
  })

  // The stage bar in every screenshot prints these descriptions (#772); the do-not-claim
  // list rules out database and cloud-storage connectors (positioning.md section 6).
  it('has in-app stage descriptions that promise no connectors', () => {
    for (const stage of WORKFLOW_STAGES) expect(stage.description).not.toMatch(/connect/i)
  })

  it('claims none of the do-not-claim list and shows no test address', () => {
    render(<HowItWorksPage />)
    const text = document.body.textContent ?? ''
    for (const pattern of [/auto-?scal/i, /ONNX|PMML/, /recipes/i, /A\/B test/i, /connect your data sources/i, /test@/i]) {
      expect(text).not.toMatch(pattern)
    }
  })
})
