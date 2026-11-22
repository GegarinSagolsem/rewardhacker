import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { Check, Copy, KeyRound, Plus, ShieldAlert } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Navigate } from 'react-router-dom'
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  ErrorBanner,
  Field,
  Input,
  Mono,
  PageHeader,
  Select,
  Skeleton,
} from '../components/ui'
import { api } from '../lib/api'
import { atLeast } from '../lib/auth'
import { timeAgo } from '../lib/format'
import { useOrg } from '../lib/org'
import type { ApiKeyCreated, Role } from '../lib/types'

function NewKey({ created, orgId, onClose }: { created: ApiKeyCreated; orgId: string; onClose: () => void }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(created.key)
      setCopied(true)
    } catch {
      /* clipboard blocked: the key is selectable */
    }
  }
  return (
    <div className="animate-in mb-6 overflow-hidden rounded-2xl border border-ink-border bg-ink text-on-ink shadow-pop">
      <div className="flex items-center gap-2.5 border-b border-ink-border px-5 py-3.5 text-[14px] font-medium">
        <ShieldAlert className="size-4 text-ring" /> Copy this key now. You won't see it again.
      </div>
      <div className="p-5">
        <div className="flex items-center gap-2 rounded-xl border border-ink-border bg-ink-2 p-1.5 pl-3">
          <code className="min-w-0 flex-1 truncate font-mono text-[12.5px] text-on-ink select-all">{created.key}</code>
          <Button size="sm" onClick={copy}>
            {copied ? <Check /> : <Copy />}
            {copied ? 'Copied' : 'Copy'}
          </Button>
        </div>
        <p className="label mt-5 text-on-ink-muted">Use it from CI or scripts</p>
        <pre className="mt-2 overflow-x-auto rounded-xl border border-ink-border bg-ink-2 p-3.5 font-mono text-[12px] leading-relaxed text-on-ink-muted">
          {`curl -H "Authorization: Bearer $RH_API_KEY" \\\n  -F file=@task.zip ${location.origin}/api/orgs/${orgId}/tasks`}
        </pre>
        <div className="mt-4 flex justify-end">
          <Button variant="ink" size="sm" onClick={onClose}>
            Done
          </Button>
        </div>
      </div>
    </div>
  )
}

export default function ApiKeys() {
  const org = useOrg()
  const qc = useQueryClient()
  const [name, setName] = useState('')
  const [role, setRole] = useState<Role>('reviewer')
  const [created, setCreated] = useState<ApiKeyCreated | null>(null)
  const keys = useQuery({ queryKey: ['api-keys', org.id], queryFn: () => api.apiKeys(org.id), enabled: org.role === 'admin' })
  const create = useMutation({
    mutationFn: () => api.createApiKey(org.id, name, role),
    onSuccess: (k) => {
      setCreated(k)
      setName('')
      qc.invalidateQueries({ queryKey: ['api-keys', org.id] })
    },
  })
  const revoke = useMutation({
    mutationFn: (id: string) => api.revokeApiKey(org.id, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['api-keys', org.id] }),
  })

  if (!atLeast(org.role, 'admin')) return <Navigate to={`/app/${org.id}/tasks`} replace />

  return (
    <div className="animate-in">
      <PageHeader
        eyebrow="Machine access"
        title="API keys"
        description="Let CI pipelines and scripts upload tasks and start runs without a person's login. Keys belong to this organization and can be viewer or reviewer, never admin."
      />

      {created && <NewKey created={created} orgId={org.id} onClose={() => setCreated(null)} />}

      <Card className="mb-6">
        <CardHeader title="Create a key" />
        <form
          onSubmit={(e: FormEvent) => {
            e.preventDefault()
            create.mutate()
          }}
          className="grid gap-4 p-4 sm:grid-cols-[1fr_auto_auto] sm:items-end sm:p-5"
        >
          <Field label="Key name">
            <Input required maxLength={100} value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. GitHub Actions" />
          </Field>
          <Field label="Role">
            <Select value={role} onChange={(e) => setRole(e.target.value as Role)} className="h-10 w-full sm:w-36">
              <option value="reviewer">Reviewer</option>
              <option value="viewer">Viewer</option>
            </Select>
          </Field>
          <Button type="submit" loading={create.isPending} className="h-10">
            {!create.isPending && <Plus />} Create key
          </Button>
        </form>
        {create.error && (
          <div className="px-4 pb-4 sm:px-5 sm:pb-5">
            <ErrorBanner>{create.error.message}</ErrorBanner>
          </div>
        )}
      </Card>

      <Card>
        <CardHeader
          title="Keys"
          aside={keys.data?.length ? <span className="font-mono text-[12px]">{keys.data.length}</span> : undefined}
        />
        {keys.isPending ? (
          <div className="p-5">
            <Skeleton className="h-10" />
          </div>
        ) : keys.error ? (
          <div className="p-5">
            <ErrorBanner>{keys.error.message}</ErrorBanner>
          </div>
        ) : keys.data.length === 0 ? (
          <EmptyState icon={<KeyRound />} title="No API keys">
            Create one above for CI.
          </EmptyState>
        ) : (
          <ul>
            {keys.data.map((k) => (
              <li
                key={k.id}
                className={clsx(
                  'flex flex-wrap items-center gap-x-4 gap-y-3 border-b border-border px-4 py-3.5 last:border-0 sm:px-5',
                  k.revoked_at && 'opacity-60',
                )}
              >
                <span className="grid size-9 shrink-0 place-items-center rounded-xl border border-border bg-bg text-muted">
                  <KeyRound className="size-4" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2 text-[14px] font-medium">
                    <span className="truncate">{k.name}</span>
                    <Badge className="capitalize">{k.role}</Badge>
                    {k.revoked_at && (
                      <Badge tone="red" mono>
                        Revoked
                      </Badge>
                    )}
                  </div>
                  <div className="mt-0.5 text-[12.5px] text-muted">
                    <Mono className="text-[12px] text-fg">{k.prefix}…</Mono> · created {timeAgo(k.created_at)} ·{' '}
                    {k.last_used_at ? `last used ${timeAgo(k.last_used_at)}` : 'never used'}
                  </div>
                </div>
                {!k.revoked_at && (
                  <Button
                    variant="danger"
                    size="sm"
                    loading={revoke.isPending && revoke.variables === k.id}
                    onClick={() => confirm(`Revoke "${k.name}"? Anything using it stops working.`) && revoke.mutate(k.id)}
                  >
                    Revoke
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
