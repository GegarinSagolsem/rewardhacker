import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Copy, KeyRound, Plus, ShieldAlert } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Navigate } from 'react-router-dom'
import { Badge, Button, Card, EmptyState, ErrorBanner, Field, Input, Mono, PageHeader, Select, Skeleton } from '../components/ui'
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
    <Card className="animate-in mb-6 border-accent/40 p-4 sm:p-5">
      <div className="flex items-center gap-2 text-[13px] font-medium">
        <ShieldAlert className="size-4 text-accent" /> Copy this key now. You won't see it again.
      </div>
      <div className="mt-3 flex items-center gap-2 rounded-lg border border-border bg-surface-2 p-2">
        <code className="min-w-0 flex-1 truncate px-1 font-mono text-[12px] select-all">{created.key}</code>
        <Button size="sm" variant="secondary" onClick={copy}>
          {copied ? <Check className="size-3.5 text-green" /> : <Copy className="size-3.5" />}
          {copied ? 'Copied' : 'Copy'}
        </Button>
      </div>
      <p className="mt-3 text-xs text-muted">Use it from CI or scripts:</p>
      <pre className="mt-1.5 overflow-x-auto rounded-lg border border-border bg-surface-2/60 p-3 font-mono text-[11.5px] leading-relaxed text-muted">
        {`curl -H "Authorization: Bearer $RH_API_KEY" \\\n  -F file=@task.zip ${location.origin}/api/orgs/${orgId}/tasks`}
      </pre>
      <div className="mt-3 flex justify-end">
        <Button variant="secondary" size="sm" onClick={onClose}>
          Done
        </Button>
      </div>
    </Card>
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
        title="API keys"
        description="Let CI pipelines and scripts upload tasks and start runs without a person's login. Keys belong to this organization and can be viewer or reviewer, never admin."
      />

      {created && <NewKey created={created} orgId={org.id} onClose={() => setCreated(null)} />}

      <Card className="mb-6 p-4">
        <form
          onSubmit={(e: FormEvent) => {
            e.preventDefault()
            create.mutate()
          }}
          className="grid gap-3 sm:grid-cols-[1fr_auto_auto] sm:items-end"
        >
          <Field label="Key name">
            <Input required maxLength={100} value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. GitHub Actions" />
          </Field>
          <Field label="Role">
            <Select value={role} onChange={(e) => setRole(e.target.value as Role)} className="h-9 w-full sm:w-32">
              <option value="reviewer">Reviewer</option>
              <option value="viewer">Viewer</option>
            </Select>
          </Field>
          <Button type="submit" loading={create.isPending} className="h-9">
            <Plus className="size-3.5" /> Create key
          </Button>
        </form>
        {create.error && (
          <div className="mt-3">
            <ErrorBanner>{create.error.message}</ErrorBanner>
          </div>
        )}
      </Card>

      <Card>
        {keys.isPending ? (
          <div className="p-4">
            <Skeleton className="h-10" />
          </div>
        ) : keys.error ? (
          <div className="p-4">
            <ErrorBanner>{keys.error.message}</ErrorBanner>
          </div>
        ) : keys.data.length === 0 ? (
          <EmptyState icon={<KeyRound className="size-4" />} title="No API keys">
            Create one above for CI.
          </EmptyState>
        ) : (
          <ul>
            {keys.data.map((k) => (
              <li key={k.id} className="flex flex-wrap items-center gap-3 border-b border-border px-4 py-3 last:border-0">
                <KeyRound className="size-4 text-muted" />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 text-[13px] font-medium">
                    <span className="truncate">{k.name}</span>
                    <Badge className="capitalize">{k.role}</Badge>
                    {k.revoked_at && <Badge tone="red">Revoked</Badge>}
                  </div>
                  <div className="text-xs text-muted">
                    <Mono>{k.prefix}…</Mono> · created {timeAgo(k.created_at)} ·{' '}
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
