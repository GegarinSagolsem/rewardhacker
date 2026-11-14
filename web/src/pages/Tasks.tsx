import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { FileArchive, FolderArchive, Upload } from 'lucide-react'
import { useRef, useState, type DragEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Button, Card, EmptyState, ErrorBanner, Mono, PageHeader, ScoreMeter, Skeleton, VerdictBadge } from '../components/ui'
import { api, ApiError } from '../lib/api'
import { atLeast } from '../lib/auth'
import { reflow, timeAgo } from '../lib/format'
import { pollWhileActive, useOrg } from '../lib/org'
import type { Run } from '../lib/types'

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
    <div className="grid gap-2">
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
          'flex w-full flex-col items-center gap-2 rounded-xl border border-dashed px-6 py-8 text-center transition-colors',
          dragging ? 'border-accent bg-accent-soft' : 'border-border-strong bg-surface hover:bg-surface-2/60',
        )}
      >
        <span className="grid size-9 place-items-center rounded-lg border border-border bg-surface-2 text-muted">
          {upload.isPending ? <Upload className="size-4 animate-bounce" /> : <FileArchive className="size-4" />}
        </span>
        <span className="text-[13px] font-medium">
          {upload.isPending ? 'Uploading and validating…' : 'Drop a task .zip here, or click to choose'}
        </span>
        <span className="max-w-md text-xs text-muted">
          The zip needs <Mono>task.yaml</Mono> at its top (or in one folder), plus the environment, tests and reference
          solution it points to. Max 20 MB.
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

  return (
    <div className="animate-in">
      <PageHeader
        title="Tasks"
        description="RL tasks uploaded to this organization. Open one to probe it for loopholes."
        actions={
          canUpload &&
          list.length > 0 && (
            <Button onClick={() => setShowUpload((v) => !v)} variant={showUpload ? 'secondary' : 'primary'}>
              <Upload className="size-3.5" /> {showUpload ? 'Cancel' : 'Upload task'}
            </Button>
          )
        }
      />

      {uploadOpen && (
        <div className="animate-in mb-6">
          <UploadZone orgId={org.id} onDone={(id) => navigate(`/app/${org.id}/tasks/${id}`)} />
        </div>
      )}

      <Card>
        {tasks.isPending ? (
          <div className="grid gap-3 p-4">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-9" />
            ))}
          </div>
        ) : tasks.error ? (
          <div className="p-4">
            <ErrorBanner>{tasks.error.message}</ErrorBanner>
          </div>
        ) : list.length === 0 ? (
          <EmptyState icon={<FolderArchive className="size-4" />} title="No tasks yet">
            {canUpload
              ? 'Upload your first task above. Try one from loopbench/tasks in the repo.'
              : 'A reviewer or admin needs to upload a task first.'}
          </EmptyState>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-[13px]">
              <thead>
                <tr className="border-b border-border text-xs text-muted">
                  <th className="px-4 py-2.5 font-medium">Task</th>
                  <th className="px-4 py-2.5 font-medium">Latest verdict</th>
                  <th className="hidden px-4 py-2.5 font-medium sm:table-cell">Score</th>
                  <th className="hidden px-4 py-2.5 font-medium md:table-cell">Runs</th>
                  <th className="px-4 py-2.5 text-right font-medium">Uploaded</th>
                </tr>
              </thead>
              <tbody>
                {list.map((t) => {
                  const run = latest.get(t.id)
                  return (
                    <tr
                      key={t.id}
                      onClick={() => navigate(`/app/${org.id}/tasks/${t.id}`)}
                      className="group cursor-pointer border-b border-border last:border-0 hover:bg-surface-2/60"
                    >
                      <td className="max-w-0 px-4 py-3 sm:w-1/2">
                        <Link
                          to={`/app/${org.id}/tasks/${t.id}`}
                          onClick={(e) => e.stopPropagation()}
                          className="font-mono text-[12.5px] font-medium group-hover:text-accent"
                        >
                          {t.spec_id}
                        </Link>
                        <div className="mt-0.5 truncate text-xs text-muted">{reflow(t.objective)}</div>
                      </td>
                      <td className="px-4 py-3">
                        {run?.status === 'queued' || run?.status === 'running' ? (
                          <span className="text-xs text-muted">{run.status}…</span>
                        ) : (
                          <VerdictBadge verdict={run?.verdict ?? null} />
                        )}
                      </td>
                      <td className="hidden px-4 py-3 sm:table-cell">
                        <ScoreMeter score={run?.score ?? null} verdict={run?.verdict ?? null} />
                      </td>
                      <td className="hidden px-4 py-3 font-mono text-xs text-muted md:table-cell">
                        {counts.get(t.id) ?? 0}
                      </td>
                      <td className="px-4 py-3 text-right text-xs whitespace-nowrap text-muted">
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
