import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Trash2, UserPlus, Users } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Badge, Button, Card, EmptyState, ErrorBanner, Field, Input, PageHeader, Select, Skeleton } from '../components/ui'
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
    <Card className="p-4">
      <form onSubmit={onSubmit} className="grid gap-3 sm:grid-cols-[1fr_auto_auto] sm:items-end">
        <Field label="Add a member by email" hint="They need a RewardHacker account first.">
          <Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="teammate@company.com" />
        </Field>
        <Field label="Role">
          <Select value={role} onChange={(e) => setRole(e.target.value as Role)} className="h-9 w-full sm:w-32">
            {ROLES.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </Select>
        </Field>
        <Button type="submit" loading={add.isPending} className="h-9 sm:mb-[22px]">
          <UserPlus className="size-3.5" /> Add
        </Button>
      </form>
      {add.error && (
        <div className="mt-3">
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
      <PageHeader title="Members" description="Who can see and change this organization's tasks and runs." />

      <div className="mb-6 grid gap-3 sm:grid-cols-3">
        {ROLES.map((r) => (
          <div key={r.value} className="rounded-xl border border-border px-4 py-3">
            <div className="text-[13px] font-medium">{r.label}</div>
            <div className="mt-0.5 text-xs text-muted">{r.help}</div>
          </div>
        ))}
      </div>

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
        {members.isPending ? (
          <div className="grid gap-3 p-4">
            <Skeleton className="h-9" />
            <Skeleton className="h-9" />
          </div>
        ) : members.error ? (
          <div className="p-4">
            <ErrorBanner>{members.error.message}</ErrorBanner>
          </div>
        ) : !members.data.length ? (
          <EmptyState icon={<Users className="size-4" />} title="No members" />
        ) : (
          <ul>
            {members.data.map((m) => {
              const self = m.user_id === me?.id
              return (
                <li key={m.user_id} className="flex flex-wrap items-center gap-3 border-b border-border px-4 py-3 last:border-0">
                  <span className="grid size-8 shrink-0 place-items-center rounded-full bg-surface-2 text-xs font-medium text-muted uppercase">
                    {m.email.slice(0, 1)}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[13px] font-medium">
                      {m.email} {self && <span className="font-normal text-muted">(you)</span>}
                    </div>
                    <div className="text-xs text-muted">Joined {timeAgo(m.created_at)}</div>
                  </div>
                  {isAdmin ? (
                    <div className="flex items-center gap-2">
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
                        aria-label={`Remove ${m.email}`}
                        title="Remove from organization"
                        onClick={() => {
                          setError(null)
                          if (confirm(`Remove ${m.email} from ${org.name}?`)) remove.mutate(m.user_id)
                        }}
                      >
                        <Trash2 className="size-3.5" />
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
