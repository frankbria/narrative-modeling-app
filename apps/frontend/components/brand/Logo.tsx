import { COMPANY } from '@/lib/legal/company'
import { cn } from '@/lib/utils'

/**
 * The SheetPredict lockup: a block of known cells whose last cell (the prediction,
 * in highlighter yellow) breaks out at the corner carrying a spreadsheet fill handle.
 * The gridline and the cut around the yellow cell are drawn in `--logo-surface`, the
 * colour behind the logo, so set it where the logo sits on anything but the page.
 */
export function Logo({ className, wordmarkClassName }: { className?: string; wordmarkClassName?: string }) {
  return (
    // One image to assistive tech, named once, so a link around it reads "SheetPredict".
    <span role="img" aria-label={COMPANY.serviceName} className={cn('inline-flex items-center gap-2 text-primary', className)}>
      <svg viewBox="0 0 32 32" className="size-[1.4em] shrink-0" aria-hidden="true">
        <rect x="2" y="2" width="20" height="20" rx="3.5" fill="currentColor" />
        <path d="M12 2v20M2 12h20" stroke="var(--logo-surface, var(--background))" strokeWidth="2.2" />
        <rect x="17" y="17" width="13" height="13" rx="2.5" fill="var(--highlight)" stroke="var(--logo-surface, var(--background))" strokeWidth="2.4" />
        <rect x="26.6" y="26.6" width="4.4" height="4.4" rx="0.8" fill="currentColor" />
      </svg>
      <span aria-hidden="true" className={cn('font-extrabold tracking-[-0.025em] text-foreground', wordmarkClassName)}>
        {COMPANY.serviceName}
      </span>
    </span>
  )
}
