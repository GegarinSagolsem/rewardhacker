import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { History, KeyRound } from 'lucide-react'
import { Link, Navigate, useSearchParams } from 'react-router-dom'
import { Card, EmptyState, ErrorBanner, Mono, PageHeader, Skeleton } from '../components/ui'
import { api } from '../lib/api'
import { atLeast } from '../lib/auth'
import { shortId, timeAgo } from '../lib/format'
import { useOrg } from '../lib/org'
import type { AuditEvent } from '../lib/types'

const FILTERS: [string | undefined, string][] = [
  [undefined, 'All'],
  ['task.', 'Tasks'],
  ['run.', 'Runs'],
  ['member.', 'Members'],
  ['export.', 'Exports'],
  ['apikey.', 'API keys'],
  ['guideline.', 'Guidelines'],
]

const s = (v: unknown) => (v == null ? '' : String(v))

function describe(e: AuditEvent, orgId: string) {
  const d = e.data ?? {}
  const runLink = e.target_id && (
    <Link to={`/app/${orgId}/runs/${e.target_id}`} className="font-mono text-[12px] hover:underline">
      {shortId(e.target_id)}
    </Link>
  )
  const taskLink = (id: string | null | undefined, label: string) =>
    id ? (
      <Link to={`/app/${orgId}/tasks/${id}`} className="font-mono text-[12px] hover:underline">
        {label}
      </Link>
    ) : (
      <Mono>{label}</Mono>
    )
  switch (e.action) {
    case 'org.create':
      return <>created the organization “{s(d.name)}”</>
    case 'member.add':
      return <>added {s(d.email)} as {s(d.role)}</>
    case 'member.role_change':
      return (
        <>
          changed {s(d.email)} from {s(d.old)} to {s(d.new)}
        </>
      )
    case 'member.remove':
      return <>removed {s(d.email)}</>
    case 'task.upload':
      return <>uploaded task {taskLink(e.target_id, s(d.spec_id))}</>
    case 'run.start':
      return (
        <>
          started run {runLink}
          {d.include_llm ? ' with the LLM adversary' : ''}
        </>
      )
    case 'export.create':
      return (
        <>
          exported <Mono>{s(d.kind)}</Mono> ({s(d.rows)} {d.rows === 1 ? 'row' : 'rows'})
        </>
      )
    case 'apikey.create':
      return (
        <>
          created API key “{s(d.name)}” ({s(d.role)})
        </>
      )
    case 'apikey.revoke':
      return <>revoked API key “{s(d.name)}”</>
    case 'guideline.add':
      return (
        <>
          added guideline “{s(d.title)}” ({s(d.chunks)} sections)
        </>
      )
    case 'guideline.delete':
      return <>deleted guideline “{s(d.title)}”</>
    case 'spec_check.run':
      return (
        <>
          ran a guideline check on {taskLink(e.target_id, s(d.spec_id) || 'task')}: {s(d.issues)} {d.issues === 1 ? 'issue' : 'issues'}
        </>
      )
    default:
      return <Mono>{e.action}</Mono>
  }
}

export default function Activity() {
  const org = useOrg()
  const [params, setParams] = useSearchParams()
  const action = params.get('action') ?? undefined
  const events = useQuery({
    queryKey: ['audit', org.id, action],
    queryFn: () => api.audit(org.id, action),
    enabled: org.role === 'admin',
  })

  if (!atLeast(org.role, 'admin')) return <Navigate to={`/app/${org.id}/tasks`} replace />

  return (
    <div className="animate-in">
      <PageHeader title="Activity" description="Who did what in this organization. Kept even after members leave." />
      <div role="tablist" aria-label="Filter activity" className="mb-4 flex flex-wrap gap-1">
        {FILTERS.map(([value, label]) => (
          <button
            key={label}
            role="tab"
            aria-selected={action === value}
            onClick={() => setParams(value ? { action: value } : {})}
            className={clsx(
              'h-7 rounded-lg px-2.5 text-xs font-medium transition-colors',
              action === value ? 'bg-fg text-bg' : 'text-muted hover:bg-surface-2 hover:text-fg',
            )}
          >
            {label}
          </button>
        ))}
      </div>
      <Card>
        {events.isPending ? (
          <div className="grid gap-3 p-4">
            <Skeleton className="h-8" />
            <Skeleton className="h-8" />
          </div>
        ) : events.error ? (
          <div className="p-4">
            <ErrorBanner>{events.error.message}</ErrorBanner>
          </div>
        ) : events.data.length === 0 ? (
          <EmptyState icon={<History className="size-4" />} title="Nothing here yet" />
        ) : (
          <ol>
            {events.data.map((e) => (
              <li key={e.id} className="flex items-start gap-3 border-b border-border px-4 py-2.5 last:border-0">
                <span className="mt-0.5 grid size-6 shrink-0 place-items-center rounded-full bg-surface-2 text-[10px] font-medium text-muted uppercase">
                  {e.actor_api_key_id ? <KeyRound className="size-3" /> : e.actor_label.slice(0, 1)}
                </span>
                <div className="min-w-0 flex-1 text-[13px]">
                  <span className="font-medium">{e.actor_label}</span>{' '}
                  <span className="text-muted">{describe(e, org.id)}</span>
                </div>
                <time className="shrink-0 text-xs whitespace-nowrap text-subtle" dateTime={e.created_at}>
                  {timeAgo(e.created_at)}
                </time>
              </li>
            ))}
          </ol>
        )}
      </Card>
    </div>
  )
}
