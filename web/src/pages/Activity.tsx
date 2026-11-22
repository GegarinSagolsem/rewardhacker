import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { History, KeyRound } from 'lucide-react'
import { Link, Navigate, useSearchParams } from 'react-router-dom'
import { Card, EmptyState, ErrorBanner, Mono, PageHeader, Segmented, Skeleton } from '../components/ui'
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
    <Link to={`/app/${orgId}/runs/${e.target_id}`} className="font-mono text-[12.5px] text-fg underline decoration-border-strong underline-offset-4 hover:decoration-accent">
      {shortId(e.target_id)}
    </Link>
  )
  const taskLink = (id: string | null | undefined, label: string) =>
    id ? (
      <Link to={`/app/${orgId}/tasks/${id}`} className="font-mono text-[12.5px] text-fg underline decoration-border-strong underline-offset-4 hover:decoration-accent">
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
      <PageHeader
        eyebrow="Audit log"
        title="Activity"
        description="Who did what in this organization. Kept even after members leave."
      />
      <Segmented
        label="Filter activity"
        options={FILTERS}
        value={action}
        onChange={(value) => setParams(value ? { action: value } : {})}
        className="mb-4"
      />
      <Card>
        {events.isPending ? (
          <div className="grid gap-3 p-5">
            <Skeleton className="h-9" />
            <Skeleton className="h-9" />
          </div>
        ) : events.error ? (
          <div className="p-5">
            <ErrorBanner>{events.error.message}</ErrorBanner>
          </div>
        ) : events.data.length === 0 ? (
          <EmptyState icon={<History />} title="Nothing here yet" />
        ) : (
          <ol>
            {events.data.map((e) => (
              <li
                key={e.id}
                className="grid grid-cols-[28px_minmax(0,1fr)_auto] items-start gap-x-3.5 gap-y-1 border-b border-border px-4 py-3.5 last:border-0 sm:px-5"
              >
                <span
                  className={clsx(
                    'mt-px grid size-7 place-items-center rounded-full border text-[11px] font-semibold uppercase',
                    e.actor_api_key_id ? 'border-ink-border bg-ink text-on-ink' : 'border-border bg-bg text-muted',
                  )}
                >
                  {e.actor_api_key_id ? <KeyRound className="size-3" /> : e.actor_label.slice(0, 1)}
                </span>
                <div className="min-w-0 text-[14px] leading-relaxed">
                  <span className="font-medium">{e.actor_label}</span>{' '}
                  <span className="text-muted">{describe(e, org.id)}</span>
                  <div className="mt-1">
                    <span className="label rounded-full bg-surface-2 px-1.5 py-0.5 text-subtle">{e.action}</span>
                  </div>
                </div>
                <time className="mt-0.5 shrink-0 text-[12.5px] whitespace-nowrap text-subtle" dateTime={e.created_at}>
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
