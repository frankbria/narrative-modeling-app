import { WALKTHROUGH_SRC } from './stageShots'

/** A silent screen capture: there is no narration, and the page says so. */
export function Walkthrough() {
  return (
    <section aria-labelledby="walkthrough-heading" id="walkthrough">
      <h2 id="walkthrough-heading">Watch a model get trained</h2>
      <p>
        The shipped customer-churn sample, from loading the file to a trained model, recorded with
        Quick training mode. It is a silent screen recording with no audio.
      </p>
      <video controls muted playsInline preload="metadata" className="w-full rounded-lg border border-border">
        <source src={WALKTHROUGH_SRC} type="video/webm" />
      </video>
    </section>
  )
}
