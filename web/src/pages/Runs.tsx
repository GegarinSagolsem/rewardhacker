import { useMutation, useQuery } from '@tanstack/react-query'
import { Download, Play } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { Menu } from '../components/Menu'
import { RunsTable } from '../components/RunsTable'
import { Button, Card, EmptyState, ErrorBanner, PageHeader, Segmented, Skeleton } from '../components/ui'
import { api, downloadExport } from '../lib/api'
import { atLeast } from '../lib/auth'
import { pollWhileActive, useOrg } from '../lib/org'
import type { ExportKind, RunStatus } from '../lib/types'

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
  const exp = useMutation({ mutationFn: (kind: ExportKind) => downloadExport(org.id, kind) })

  return (
    <div className="animate-in">
      <PageHeader
        eyebrow={
          runs.isSuccess
            ? [String(runs.data.length), status, runs.data.length === 1 ? 'run' : 'runs'].filter(Boolean).join(' ')
            : 'Runs'
        }
        title="Runs"
        description="Every probe run in this organization, newest first."
        actions={
          atLeast(org.role, 'reviewer') && (
            <Menu
              trigger={({ toggle, open }) => (
                <Button variant="secondary" onClick={toggle} aria-expanded={open} loading={exp.isPending}>
                  {!exp.isPending && <Download />} Export
                </Button>
              )}
              items={[
                { label: 'All runs as CSV', hint: 'One row per run, for spreadsheets', onSelect: () => exp.mutate('runs.csv') },
                {
                  label: 'All runs as JSON Lines',
                  hint: 'Full reports, for pipelines',
                  onSelect: () => exp.mutate('runs.jsonl'),
                },
              ]}
            />
          )
        }
      />
      {exp.error && (
        <div className="mb-4">
          <ErrorBanner>{exp.error.message}</ErrorBanner>
        </div>
      )}

      <Segmented
        label="Filter by status"
        options={FILTERS}
        value={status}
        onChange={(value) => setParams(value ? { status: value } : {})}
        className="mb-4"
      />

      <Card className="overflow-hidden">
        {runs.isPending ? (
          <div className="grid gap-3 p-5">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-10" />
            ))}
          </div>
        ) : runs.error ? (
          <div className="p-5">
            <ErrorBanner>{runs.error.message}</ErrorBanner>
          </div>
        ) : runs.data.length === 0 ? (
          <EmptyState icon={<Play />} title={status ? `No ${status} runs` : 'No runs yet'}>
            Open a task and start a run to probe it.
          </EmptyState>
        ) : (
          <RunsTable orgId={org.id} runs={runs.data} tasks={tasks.data ?? []} />
        )}
      </Card>
    </div>
  )
}
