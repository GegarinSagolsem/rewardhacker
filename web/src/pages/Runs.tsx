import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { Play } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { RunsTable } from '../components/RunsTable'
import { Card, EmptyState, ErrorBanner, PageHeader, Skeleton } from '../components/ui'
import { api } from '../lib/api'
import { pollWhileActive, useOrg } from '../lib/org'
import type { RunStatus } from '../lib/types'

const FILTERS: [RunStatus | undefined, string][] = [
  [undefined, 'All'],
  ['queued', 'Queued'],
  ['running', 'Running'],
  ['done', 'Done'],
  ['failed', 'Failed'],
]

export default function Runs() {
  const org = useOrg()
  const [params, setParams] = useSearchParams()
  const status = (params.get('status') as RunStatus | null) ?? undefined

  const runs = useQuery({
    queryKey: ['runs', org.id, { status }],
    queryFn: () => api.runs(org.id, { status }),
    refetchInterval: (q) => pollWhileActive(q.state.data) || (status === 'queued' || status === 'running' ? 2500 : false),
  })
  const tasks = useQuery({ queryKey: ['tasks', org.id], queryFn: () => api.tasks(org.id) })

  return (
    <div className="animate-in">
      <PageHeader title="Runs" description="Every probe run in this organization, newest first." />

      <div role="tablist" aria-label="Filter by status" className="mb-4 flex flex-wrap gap-1">
        {FILTERS.map(([value, label]) => (
          <button
            key={label}
            role="tab"
            aria-selected={status === value}
            onClick={() => setParams(value ? { status: value } : {})}
            className={clsx(
              'h-7 rounded-lg px-2.5 text-xs font-medium transition-colors',
              status === value
                ? 'bg-fg text-bg'
                : 'text-muted hover:bg-surface-2 hover:text-fg',
            )}
          >
            {label}
          </button>
        ))}
      </div>

      <Card>
        {runs.isPending ? (
          <div className="grid gap-3 p-4">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-9" />
            ))}
          </div>
        ) : runs.error ? (
          <div className="p-4">
            <ErrorBanner>{runs.error.message}</ErrorBanner>
          </div>
        ) : runs.data.length === 0 ? (
          <EmptyState icon={<Play className="size-4" />} title={status ? `No ${status} runs` : 'No runs yet'}>
            Open a task and start a run to probe it.
          </EmptyState>
        ) : (
          <RunsTable orgId={org.id} runs={runs.data} tasks={tasks.data ?? []} />
        )}
      </Card>
    </div>
  )
}
