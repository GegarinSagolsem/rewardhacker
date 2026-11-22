import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { ArrowUpRight, FileArchive, FolderArchive, Upload, X } from 'lucide-react'
import { useRef, useState, type DragEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { TBODY_ROW, TD, TH, THEAD_ROW } from '../components/RunsTable'
import { toneFill, verdictTone } from '../components/styles'
import {
  Button,
  Card,
  EmptyState,
  ErrorBanner,
  Mono,
  PageHeader,
  ScoreMeter,
  Skeleton,
  StatusBadge,
  VerdictBadge,
} from '../components/ui'
import { api, ApiError } from '../lib/api'
import { atLeast } from '../lib/auth'
import { reflow, timeAgo } from '../lib/format'
import { pollWhileActive, useOrg } from '../lib/org'
import type { Run, Verdict } from '../lib/types'

function UploadZone({ orgId, onDone }: { orgId: string; onDone: (taskId: string) => void }) {
  const qc = useQueryClient()
  const input = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const upload = useMutation({
    mutationFn: (file: File) => api.uploadTask(orgId, file),
    onSuccess: (task) => {
      qc.invalidateQueries({ queryKey: ['tasks', orgId] })
      onDone(task.id)
    },
  })

  const pick = (files: FileList | null) => {
    const f = files?.[0]
    if (f) upload.mutate(f)
  }
  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setDragging(false)
    pick(e.dataTransfer.files)
  }

  return (
    <div className="grid gap-2.5">
      <button
        type="button"
        onClick={() => input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        disabled={upload.isPending}
        className={clsx(
          'group relative flex w-full flex-col items-center gap-3 overflow-hidden rounded-2xl border-[1.5px] border-dashed px-6 py-12 text-center transition-colors',
          dragging ? 'border-accent bg-accent-soft' : 'border-border-strong bg-surface hover:border-fg/40',
        )}
      >
        <span aria-hidden className="bg-graph pointer-events-none absolute inset-0 opacity-60 [mask-image:radial-gradient(60%_80%_at_50%_50%,black,transparent)]" />
        <span
          className={clsx(
            'relative grid size-12 place-items-center rounded-xl border transition-colors',
            dragging || upload.isPending
              ? 'border-accent bg-accent text-accent-fg'
              : 'border-ink-border bg-ink text-on-ink group-hover:bg-accent group-hover:border-accent',
          )}
        >
          {upload.isPending ? <Upload className="size-5 animate-bounce" /> : <FileArchive className="size-5" />}
        </span>
        <span className="relative text-[15px] font-semibold tracking-tight">
          {upload.isPending ? 'Uploading and validating…' : 'Drop a task .zip here, or click to choose'}
        </span>
        <span className="relative max-w-md text-[13px] leading-relaxed text-muted">
          The zip needs <Mono className="text-fg">task.yaml</Mono> at its top (or in one folder), plus the environment,
          tests and reference solution it points to. Max 20 MB.
        </span>
      </button>
      <input
        ref={input}
        type="file"
        accept=".zip,application/zip"
        className="hidden"
        onChange={(e) => {
          pick(e.target.files)
          e.target.value = ''
        }}
      />
      {upload.error && (
        <ErrorBanner>
          <span className="font-medium">Upload rejected.</span>{' '}
          {upload.error instanceof ApiError ? upload.error.message : 'Unknown error.'}
        </ErrorBanner>
      )}
    </div>
  )
}

const SUMMARY: [Verdict | 'unprobed', string][] = [
  ['exploitable', 'Exploitable'],
  ['broken', 'Broken'],
  ['flaky', 'Flaky'],
  ['robust', 'Robust'],
  ['inconclusive', 'Inconclusive'],
  ['unprobed', 'Not probed'],
]

/** Counts of each task's latest verdict: the state of the task set at a glance. */
function VerdictSummary({ counts, total }: { counts: Map<string, number>; total: number }) {
  return (
    <div className="mb-6 grid grid-cols-2 gap-px overflow-hidden rounded-2xl border border-border bg-border shadow-card sm:grid-cols-3 lg:grid-cols-6">
      {SUMMARY.map(([key, label]) => {
        const n = counts.get(key) ?? 0
        const fill = key === 'unprobed' ? 'bg-transparent ring-1 ring-inset ring-border-strong' : toneFill[verdictTone[key]]
        return (
          <div key={key} className="min-w-0 bg-surface px-4 py-4 sm:px-5">
            <div className="label flex items-center gap-2 text-muted">
              <span aria-hidden className={clsx('size-2 rounded-full', fill)} />
              {label}
            </div>
            <div className={clsx('mt-2.5 text-[26px] leading-none font-semibold tracking-[-0.03em] tabular-nums', n === 0 && 'text-subtle')}>
              {n}
              {key === 'unprobed' && total > 0 && <span className="ml-1 text-[13px] font-normal text-subtle">/ {total}</span>}
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default function Tasks() {
  const org = useOrg()
  const navigate = useNavigate()
  const canUpload = atLeast(org.role, 'reviewer')
  const [showUpload, setShowUpload] = useState(false)

  const tasks = useQuery({ queryKey: ['tasks', org.id], queryFn: () => api.tasks(org.id) })
  const runs = useQuery({
    queryKey: ['runs', org.id],
    queryFn: () => api.runs(org.id),
    refetchInterval: (q) => pollWhileActive(q.state.data),
  })

  // Runs come newest first: the first one seen per task is its latest.
  const latest = new Map<string, Run>()
  const counts = new Map<string, number>()
  for (const r of runs.data ?? []) {
    if (!latest.has(r.task_id)) latest.set(r.task_id, r)
    counts.set(r.task_id, (counts.get(r.task_id) ?? 0) + 1)
  }

  const list = tasks.data ?? []
  const uploadOpen = showUpload || (canUpload && tasks.isSuccess && list.length === 0)

  const verdictCounts = new Map<string, number>()
  for (const t of list) {
    const v = latest.get(t.id)?.verdict ?? 'unprobed'
    verdictCounts.set(v, (verdictCounts.get(v) ?? 0) + 1)
  }

  return (
    <div className="animate-in">
      <PageHeader
        eyebrow={tasks.isSuccess ? `${list.length} ${list.length === 1 ? 'task' : 'tasks'}` : 'Tasks'}
        title="Tasks"
        description="RL tasks uploaded to this organization. Open one to probe it for loopholes."
        actions={
          canUpload &&
          list.length > 0 && (
            <Button onClick={() => setShowUpload((v) => !v)} variant={showUpload ? 'secondary' : 'primary'}>
              {showUpload ? <X /> : <Upload />} {showUpload ? 'Cancel' : 'Upload task'}
            </Button>
          )
        }
      />

      {uploadOpen && (
        <div className="animate-in mb-6">
          <UploadZone orgId={org.id} onDone={(id) => navigate(`/app/${org.id}/tasks/${id}`)} />
        </div>
      )}

      {list.length > 0 && runs.isSuccess && <VerdictSummary counts={verdictCounts} total={list.length} />}

      <Card className="overflow-hidden">
        {tasks.isPending ? (
          <div className="grid gap-3 p-5">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-10" />
            ))}
          </div>
        ) : tasks.error ? (
          <div className="p-5">
            <ErrorBanner>{tasks.error.message}</ErrorBanner>
          </div>
        ) : list.length === 0 ? (
          <EmptyState icon={<FolderArchive />} title="No tasks yet">
            {canUpload
              ? 'Upload your first task above. Try one from loopbench/tasks in the repo.'
              : 'A reviewer or admin needs to upload a task first.'}
          </EmptyState>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[13.5px]">
              <thead>
                <tr className={THEAD_ROW}>
                  <th className={TH}>Task</th>
                  <th className={TH}>Latest verdict</th>
                  <th className={`${TH} hidden sm:table-cell`}>Score</th>
                  <th className={`${TH} hidden md:table-cell`}>Runs</th>
                  <th className={`${TH} hidden text-right sm:table-cell`}>Uploaded</th>
                </tr>
              </thead>
              <tbody>
                {list.map((t) => {
                  const run = latest.get(t.id)
                  return (
                    <tr key={t.id} onClick={() => navigate(`/app/${org.id}/tasks/${t.id}`)} className={TBODY_ROW}>
                      <td className={`${TD} w-full max-w-0 sm:w-1/2`}>
                        <Link
                          to={`/app/${org.id}/tasks/${t.id}`}
                          onClick={(e) => e.stopPropagation()}
                          className="inline-flex max-w-full items-center gap-1 font-mono text-[13px] font-medium group-hover:text-accent-ink"
                        >
                          <span className="truncate">{t.spec_id}</span>
                          <ArrowUpRight className="size-3 opacity-0 transition-opacity group-hover:opacity-100" />
                        </Link>
                        <div className="mt-1 truncate text-[12.5px] text-muted">{reflow(t.objective)}</div>
                      </td>
                      <td className={TD}>
                        {run?.status === 'queued' || run?.status === 'running' ? (
                          <StatusBadge status={run.status} />
                        ) : (
                          <VerdictBadge verdict={run?.verdict ?? null} />
                        )}
                      </td>
                      <td className={`${TD} hidden sm:table-cell`}>
                        <ScoreMeter score={run?.score ?? null} verdict={run?.verdict ?? null} />
                      </td>
                      <td className={`${TD} hidden font-mono text-[12.5px] text-muted md:table-cell`}>
                        {counts.get(t.id) ?? 0}
                      </td>
                      <td className={`${TD} hidden text-right text-[12.5px] whitespace-nowrap text-muted sm:table-cell`}>
                        {timeAgo(t.created_at)}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
