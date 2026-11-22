import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { Trash2, UserPlus, Users } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  ErrorBanner,
  Field,
  Input,
  PageHeader,
  Select,
  Skeleton,
} from '../components/ui'
import { api } from '../lib/api'
import { atLeast, useAuth } from '../lib/auth'
import { timeAgo } from '../lib/format'
import { useOrg } from '../lib/org'
import type { Role } from '../lib/types'

const ROLES: { value: Role; label: string; help: string }[] = [
  { value: 'viewer', label: 'Viewer', help: 'Reads tasks, runs and reports.' },
  { value: 'reviewer', label: 'Reviewer', help: 'Also uploads tasks and starts runs.' },
  { value: 'admin', label: 'Admin', help: 'Also manages members.' },
]

function AddMember({ orgId }: { orgId: string }) {
  const qc = useQueryClient()
  const [email, setEmail] = useState('')
  const [role, setRole] = useState<Role>('reviewer')
  const add = useMutation({
    mutationFn: () => api.addMember(orgId, email, role),
    onSuccess: () => {
      setEmail('')
      qc.invalidateQueries({ queryKey: ['members', orgId] })
    },
  })
  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    add.mutate()
  }
  return (
    <Card>
      <CardHeader title="Invite" />
      <form onSubmit={onSubmit} className="grid gap-4 p-4 sm:grid-cols-[1fr_auto_auto] sm:items-start sm:p-5">
        <Field label="Add a member by email" hint="They need a RewardHacker account first.">
          <Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="teammate@company.com" />
        </Field>
        <Field label="Role">
          <Select value={role} onChange={(e) => setRole(e.target.value as Role)} className="h-10 w-full sm:w-36">
            {ROLES.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </Select>
        </Field>
        <Button type="submit" loading={add.isPending} className="h-10 sm:mt-[26px]">
          {!add.isPending && <UserPlus />} Add member
        </Button>
      </form>
      {add.error && (
        <div className="px-4 pb-4 sm:px-5 sm:pb-5">
          <ErrorBanner>{add.error.message}</ErrorBanner>
        </div>
      )}
    </Card>
  )
}

export default function Members() {
  const org = useOrg()
  const { me } = useAuth()
  const qc = useQueryClient()
  const isAdmin = atLeast(org.role, 'admin')
  const members = useQuery({ queryKey: ['members', org.id], queryFn: () => api.members(org.id) })
  const [error, setError] = useState<string | null>(null)

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['members', org.id] })
    qc.invalidateQueries({ queryKey: ['me'] })
  }
  const update = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: Role }) => api.updateMember(org.id, userId, role),
    onSuccess: refresh,
    onError: (e) => setError(e.message),
  })
  const remove = useMutation({
    mutationFn: (userId: string) => api.removeMember(org.id, userId),
    onSuccess: refresh,
    onError: (e) => setError(e.message),
  })

  return (
    <div className="animate-in">
      <PageHeader
        eyebrow={members.isSuccess ? `${members.data.length} ${members.data.length === 1 ? 'member' : 'members'}` : 'Members'}
        title="Members"
        description="Who can see and change this organization's tasks and runs."
      />

      <ol className="mb-8 grid gap-px overflow-hidden rounded-2xl border border-border bg-border sm:grid-cols-3">
        {ROLES.map((r, i) => (
          <li key={r.value} className={clsx('bg-surface px-5 py-4', org.role === r.value && 'bg-bg')}>
            <div className="flex items-center gap-2">
              <span className="font-mono text-[11px] text-subtle">0{i + 1}</span>
              <span className="text-[14.5px] font-semibold tracking-tight">{r.label}</span>
              {org.role === r.value && (
                <Badge tone="accent" className="ml-auto">
                  You
                </Badge>
              )}
            </div>
            <div className="mt-1 text-[13px] text-muted">{r.help}</div>
          </li>
        ))}
      </ol>

      {isAdmin && (
        <div className="mb-6">
          <AddMember orgId={org.id} />
        </div>
      )}
      {error && (
        <div className="mb-4">
          <ErrorBanner>{error}</ErrorBanner>
        </div>
      )}

      <Card>
        <CardHeader title="People" />
        {members.isPending ? (
          <div className="grid gap-3 p-5">
            <Skeleton className="h-10" />
            <Skeleton className="h-10" />
          </div>
        ) : members.error ? (
          <div className="p-5">
            <ErrorBanner>{members.error.message}</ErrorBanner>
          </div>
        ) : !members.data.length ? (
          <EmptyState icon={<Users />} title="No members" />
        ) : (
          <ul>
            {members.data.map((m) => {
              const self = m.user_id === me?.id
              return (
                <li
                  key={m.user_id}
                  className="flex flex-wrap items-center gap-x-4 gap-y-3 border-b border-border px-4 py-3.5 last:border-0 sm:px-5"
                >
                  <span className="grid size-9 shrink-0 place-items-center rounded-full border border-border bg-bg text-[13px] font-semibold text-muted uppercase">
                    {m.email.slice(0, 1)}
                  </span>
                  <div className="min-w-0 flex-1 max-sm:basis-[calc(100%-52px)]">
                    <div className="truncate text-[14px] font-medium">
                      {m.email} {self && <span className="font-normal text-muted">(you)</span>}
                    </div>
                    <div className="mt-0.5 text-[12.5px] text-muted">Joined {timeAgo(m.created_at)}</div>
                  </div>
                  {isAdmin ? (
                    <div className="flex items-center gap-2 max-sm:ml-[52px]">
                      <Select
                        aria-label={`Role for ${m.email}`}
                        value={m.role}
                        disabled={update.isPending}
                        onChange={(e) => {
                          setError(null)
                          update.mutate({ userId: m.user_id, role: e.target.value as Role })
                        }}
                      >
                        {ROLES.map((r) => (
                          <option key={r.value} value={r.value}>
                            {r.label}
                          </option>
                        ))}
                      </Select>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="size-9 px-0"
                        aria-label={`Remove ${m.email}`}
                        title="Remove from organization"
                        onClick={() => {
                          setError(null)
                          if (confirm(`Remove ${m.email} from ${org.name}?`)) remove.mutate(m.user_id)
                        }}
                      >
                        <Trash2 />
                      </Button>
                    </div>
                  ) : (
                    <Badge className="capitalize">{m.role}</Badge>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </Card>
    </div>
  )
}
