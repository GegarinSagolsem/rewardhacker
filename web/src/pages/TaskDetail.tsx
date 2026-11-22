import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { ArrowLeft, Check, Lock, Play, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { RunsTable } from '../components/RunsTable'
import { SpecCheckPanel } from '../components/SpecCheckPanel'
import { Button, Card, CardHeader, EmptyState, ErrorBanner, Mono, PageHeader, Skeleton } from '../components/ui'
import { api } from '../lib/api'
import { atLeast } from '../lib/auth'
import { reflow, shortId, timeAgo } from '../lib/format'
import { pollWhileActive, useOrg } from '../lib/org'

/** The static probes every run executes, in the order the report lists them. */
const STATIC_PROBES = [
  'null',
  'reference',
  'rewrite-tests',
  'pytest-forcepass',
  'python-startup-hook',
  'shadow-runner',
  'lingering-process',
  'verifier-file-tamper',
]

function StartRun({ orgId, taskId, aiEnabled }: { orgId: string; taskId: string; aiEnabled: boolean }) {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [llm, setLlm] = useState(false)
  const start = useMutation({
    mutationFn: () => api.startRun(orgId, taskId, llm && aiEnabled),
    onSuccess: (run) => {
      qc.invalidateQueries({ queryKey: ['runs', orgId] })
      navigate(`/app/${orgId}/runs/${run.id}`)
    },
  })
  const withAdversary = llm && aiEnabled

  return (
    <div className="overflow-hidden rounded-2xl border border-ink-border bg-ink text-on-ink shadow-pop">
      <div className="border-b border-ink-border px-5 pt-5 pb-4">
        <div className="label flex items-center gap-2 text-on-ink-muted">
          <span className="size-1.5 bg-ring rounded-full" aria-hidden /> Probe this task
        </div>
        <h2 className="mt-3 text-[20px] leading-tight font-semibold tracking-[-0.02em]">Attack it before training does.</h2>
        <p className="mt-2 text-[13px] leading-relaxed text-on-ink-muted">
          Each probe runs in its own throwaway, network-less Docker container: a no-op agent, the reference solution,
          flakiness and six tamper attacks.
        </p>
      </div>

      <ul className="grid grid-cols-2 gap-x-3 gap-y-1.5 border-b border-ink-border px-5 py-4" aria-label="Probes in this run">
        {STATIC_PROBES.map((p) => (
          <li key={p} className="flex min-w-0 items-center gap-1.5 font-mono text-[11px] text-on-ink-muted">
            <Check className="size-3 shrink-0 text-green-fill" />
            <span className="truncate" title={p}>{p}</span>
          </li>
        ))}
        <li
          className={clsx(
            'col-span-2 flex items-center gap-1.5 font-mono text-[11px] transition-colors',
            withAdversary ? 'text-on-ink' : 'text-on-ink-muted/50 line-through',
          )}
        >
          <Sparkles className={clsx('size-3 shrink-0', withAdversary ? 'text-ring' : '')} />
          llm-adversary
        </li>
      </ul>

      <div className="px-5 py-4">
        <label
          className={clsx(
            'flex items-start gap-3 rounded-xl border p-3 transition-colors',
            !aiEnabled
              ? 'cursor-not-allowed border-ink-border opacity-70'
              : withAdversary
                ? 'cursor-pointer border-ring/60 bg-ink-2'
                : 'cursor-pointer border-ink-border hover:bg-ink-2',
          )}
        >
          <input
            type="checkbox"
            disabled={!aiEnabled}
            checked={withAdversary}
            onChange={(e) => setLlm(e.target.checked)}
            className="mt-0.5 size-4 shrink-0 accent-[var(--accent)]"
          />
          <span>
            <span className="flex items-center gap-1.5 text-[13.5px] font-medium">
              {aiEnabled ? <Sparkles className="size-3.5 text-ring" /> : <Lock className="size-3.5" />} Add the LLM
              adversary
            </span>
            <span className="mt-1 block text-[12.5px] leading-relaxed text-on-ink-muted">
              {aiEnabled
                ? 'A Gemini agent tries to earn the reward without doing the work, and a judge checks the result. About $0.002 per run, hard-capped at $0.05.'
                : 'Not enabled for this organization. AI features are opt-in on the public demo to keep costs bounded; the static probes are free.'}
            </span>
          </span>
        </label>
        {start.error && (
          <div className="mt-3">
            <ErrorBanner>{start.error.message}</ErrorBanner>
          </div>
        )}
        <Button size="lg" className="mt-4 w-full" onClick={() => start.mutate()} loading={start.isPending}>
          {!start.isPending && <Play />} Start run
        </Button>
        <p className="mt-3 text-center text-[11.5px] leading-relaxed text-on-ink-muted">
          Runs are queued; a worker (<Mono className="text-[11px] text-on-ink">rh worker</Mono>, or a cloud build in
          production) executes them.
        </p>
      </div>
    </div>
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
        className="mb-5 inline-flex items-center gap-1.5 text-[13px] text-muted hover:text-fg"
      >
        <ArrowLeft className="size-3.5" /> All tasks
      </Link>
      <PageHeader
        title={
          task.data ? (
            <span className="font-mono text-[22px] font-semibold tracking-[-0.02em] break-all sm:text-[28px]">
              {task.data.spec_id}
            </span>
          ) : (
            <Skeleton className="h-8 w-56" />
          )
        }
        eyebrow={
          task.data ? (
            <>
              Task {shortId(task.data.id)} · uploaded {timeAgo(task.data.created_at)}
            </>
          ) : (
            'Task'
          )
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_340px] lg:gap-8">
        <div className="grid min-w-0 grid-cols-1 content-start gap-6">
          <Card>
            <CardHeader title="Objective given to the agent" />
            {task.data ? (
              <p className="max-w-[72ch] px-4 py-5 text-[15px] leading-[1.7] break-words whitespace-pre-wrap sm:px-5">
                {reflow(task.data.objective)}
              </p>
            ) : (
              <div className="grid gap-2 p-5">
                <Skeleton className="h-4" />
                <Skeleton className="h-4 w-2/3" />
              </div>
            )}
          </Card>

          <Card className="overflow-hidden">
            <CardHeader
              title="Runs"
              aside={runs.data?.length ? <span className="font-mono text-[12px]">{runs.data.length}</span> : undefined}
            />
            {runs.data?.length ? (
              <RunsTable orgId={org.id} runs={runs.data} compact />
            ) : runs.isPending ? (
              <div className="p-5">
                <Skeleton className="h-10" />
              </div>
            ) : (
              <EmptyState icon={<Play />} title="Not probed yet">
                Start a run to find out whether this task's reward can be earned without doing the work.
              </EmptyState>
            )}
          </Card>

          <SpecCheckPanel orgId={org.id} taskId={taskId} canRun={atLeast(org.role, 'reviewer') && org.llm_enabled} />
        </div>

        {atLeast(org.role, 'reviewer') && (
          <div className="lg:sticky lg:top-24 lg:self-start">
            <StartRun orgId={org.id} taskId={taskId} aiEnabled={org.llm_enabled} />
          </div>
        )}
      </div>
    </div>
  )
}
