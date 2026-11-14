import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { ArrowLeft, Play, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { RunsTable } from '../components/RunsTable'
import { SpecCheckPanel } from '../components/SpecCheckPanel'
import { Button, Card, EmptyState, ErrorBanner, Mono, PageHeader, Skeleton } from '../components/ui'
import { api } from '../lib/api'
import { atLeast } from '../lib/auth'
import { reflow, shortId, timeAgo } from '../lib/format'
import { pollWhileActive, useOrg } from '../lib/org'

function StartRun({ orgId, taskId }: { orgId: string; taskId: string }) {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [llm, setLlm] = useState(false)
  const start = useMutation({
    mutationFn: () => api.startRun(orgId, taskId, llm),
    onSuccess: (run) => {
      qc.invalidateQueries({ queryKey: ['runs', orgId] })
      navigate(`/app/${orgId}/runs/${run.id}`)
    },
  })

  return (
    <Card className="p-4">
      <div className="text-[13px] font-medium">Probe this task</div>
      <p className="mt-1 text-xs text-muted">
        Runs the static probes in throwaway Docker containers: no-op agent, reference solution, flakiness and six
        tamper attacks.
      </p>
      <label
        className={clsx(
          'mt-4 flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors',
          llm ? 'border-accent/40 bg-accent-soft' : 'border-border hover:bg-surface-2/60',
        )}
      >
        <input
          type="checkbox"
          checked={llm}
          onChange={(e) => setLlm(e.target.checked)}
          className="mt-0.5 size-4 accent-[var(--accent)]"
        />
        <span>
          <span className="flex items-center gap-1.5 text-[13px] font-medium">
            <Sparkles className="size-3.5 text-accent" /> Add the LLM adversary
          </span>
          <span className="mt-0.5 block text-xs text-muted">
            A Gemini agent tries to earn the reward without doing the work, and a judge checks the result. About $0.002
            per run, hard-capped at $0.05.
          </span>
        </span>
      </label>
      {start.error && (
        <div className="mt-3">
          <ErrorBanner>{start.error.message}</ErrorBanner>
        </div>
      )}
      <Button className="mt-4 w-full" onClick={() => start.mutate()} loading={start.isPending}>
        <Play className="size-3.5" /> Start run
      </Button>
      <p className="mt-2 text-center text-[11px] text-subtle">
        Runs are queued; a worker (<Mono>rh worker</Mono>) executes them.
      </p>
    </Card>
  )
}

export default function TaskDetail() {
  const org = useOrg()
  const { taskId = '' } = useParams()
  const task = useQuery({ queryKey: ['task', org.id, taskId], queryFn: () => api.task(org.id, taskId) })
  const runs = useQuery({
    queryKey: ['runs', org.id, { taskId }],
    queryFn: () => api.runs(org.id, { taskId }),
    refetchInterval: (q) => pollWhileActive(q.state.data),
  })

  if (task.error) return <ErrorBanner>{task.error.message}</ErrorBanner>

  return (
    <div className="animate-in">
      <Link
        to={`/app/${org.id}/tasks`}
        className="mb-4 inline-flex items-center gap-1 text-[13px] text-muted hover:text-fg"
      >
        <ArrowLeft className="size-3.5" /> Tasks
      </Link>
      <PageHeader
        title={task.data ? <span className="font-mono text-lg">{task.data.spec_id}</span> : <Skeleton className="h-7 w-48" />}
        eyebrow={
          task.data && (
            <>
              Task <Mono>{shortId(task.data.id)}</Mono> · uploaded {timeAgo(task.data.created_at)}
            </>
          )
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="grid min-w-0 grid-cols-1 content-start gap-6">
          <Card>
            <div className="border-b border-border px-4 py-2.5 text-xs font-medium text-muted">Objective given to the agent</div>
            {task.data ? (
              <p className="px-4 py-4 text-[13px] leading-relaxed break-words whitespace-pre-wrap">
                {reflow(task.data.objective)}
              </p>
            ) : (
              <div className="grid gap-2 p-4">
                <Skeleton className="h-4" />
                <Skeleton className="h-4 w-2/3" />
              </div>
            )}
          </Card>

          <Card>
            <div className="border-b border-border px-4 py-2.5 text-xs font-medium text-muted">Runs</div>
            {runs.data?.length ? (
              <RunsTable orgId={org.id} runs={runs.data} />
            ) : runs.isPending ? (
              <div className="p-4">
                <Skeleton className="h-9" />
              </div>
            ) : (
              <EmptyState icon={<Play className="size-4" />} title="Not probed yet">
                Start a run to find out whether this task's reward can be earned without doing the work.
              </EmptyState>
            )}
          </Card>

          <SpecCheckPanel orgId={org.id} taskId={taskId} canRun={atLeast(org.role, 'reviewer')} />
        </div>

        {atLeast(org.role, 'reviewer') && (
          <div className="lg:sticky lg:top-10 lg:self-start">
            <StartRun orgId={org.id} taskId={taskId} />
          </div>
        )}
      </div>
    </div>
  )
}
