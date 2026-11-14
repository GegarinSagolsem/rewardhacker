import { useOutletContext } from 'react-router-dom'
import type { Org } from './types'

/** The org selected in the URL (provided by the org-scoped layout). */
export const useOrg = () => useOutletContext<Org>()

/** Poll while anything is still queued or running. */
export const pollWhileActive = (items: { status: string }[] | undefined) =>
  items?.some((r) => r.status === 'queued' || r.status === 'running') ? 2500 : false
