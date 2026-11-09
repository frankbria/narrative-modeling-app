'use client'

import { createContext, useContext, type ReactNode } from 'react'

const InAppShell = createContext(false)

/** Marks the signed-in shell (sidebar and sheet tabs), so public chrome inside it can step aside (#1190). */
export function AppShellProvider({ children }: { children: ReactNode }) {
  return <InAppShell.Provider value={true}>{children}</InAppShell.Provider>
}

export const useInAppShell = () => useContext(InAppShell)
