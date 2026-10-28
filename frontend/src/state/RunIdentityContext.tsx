import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

/** The header band carries whichever run is on screen, so an examiner can
 * read the identifier out loud while asking about it ("run 0231, option
 * B"). Pages publish their identity here and clear it on the way out; the
 * header is the only consumer. */
type RunIdentityValue = {
  identity: string | null
  setIdentity: (identity: string | null) => void
}

const RunIdentityContext = createContext<RunIdentityValue>({ identity: null, setIdentity: () => {} })

export function RunIdentityProvider({ children }: { children: ReactNode }) {
  const [identity, setIdentity] = useState<string | null>(null)
  const value = useMemo(() => ({ identity, setIdentity }), [identity])
  return <RunIdentityContext.Provider value={value}>{children}</RunIdentityContext.Provider>
}

export function useRunIdentity() {
  return useContext(RunIdentityContext)
}

/** Publishes a run identifier into the header for as long as the calling
 * page is mounted. `null` leaves the band showing nothing rather than a
 * placeholder. */
export function usePublishRunIdentity(identity: string | null) {
  const { setIdentity } = useRunIdentity()
  const publish = useCallback(setIdentity, [setIdentity])

  useEffect(() => {
    publish(identity)
    return () => publish(null)
  }, [identity, publish])
}

/** A simulation UUID shortened to the run number the sheet prints
 * everywhere: the first eight characters, upper-cased, as the report
 * filenames already use (`downloadReport`). */
export function runCode(simulationId: string): string {
  return `RUN ${simulationId.slice(0, 8).toUpperCase()}`
}
