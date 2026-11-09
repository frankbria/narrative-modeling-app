import { HugeiconsIcon as LibraryIcon, type HugeiconsIconProps } from '@hugeicons/react';

/** The app's one icon renderer: hidden from assistive tech unless it is given an `aria-label` (lucide's default, #1177). */
export function HugeiconsIcon(props: HugeiconsIconProps) {
  return <LibraryIcon aria-hidden={props['aria-label'] === undefined} {...props} />;
}
