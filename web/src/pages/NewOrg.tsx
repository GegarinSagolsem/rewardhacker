import { useQueryClient } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Button, Card, ErrorBanner, Field, Input, Logo, ThemeToggle } from '../components/ui'
import { api, ApiError } from '../lib/api'
import { useAuth } from '../lib/auth'

export default function NewOrg() {
  const { me, logout } = useAuth()
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const first = !me?.orgs.length

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const org = await api.createOrg(name)
      await qc.invalidateQueries({ queryKey: ['me'] })
      navigate(`/app/${org.id}/tasks`, { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not create the organization.')
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="flex items-center justify-between px-4 py-4 sm:px-6">
        <Logo className="text-[15px]" />
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <Button variant="ghost" size="sm" onClick={logout}>
            Sign out
          </Button>
        </div>
      </header>
      <main className="grid flex-1 place-items-center px-4 pb-16">
        <div className="animate-in w-full max-w-[420px]">
          {!first && (
            <Link to="/app" className="mb-4 inline-flex items-center gap-1 text-[13px] text-muted hover:text-fg">
              <ArrowLeft className="size-3.5" /> Back
            </Link>
          )}
          <h1 className="text-xl font-semibold tracking-tight">
            {first ? 'Create your first organization' : 'New organization'}
          </h1>
          <p className="mt-1 text-[13px] text-muted">
            Tasks, runs and reports belong to an organization. You'll be its admin and can invite reviewers and
            viewers.
          </p>
          <Card className="mt-6 p-5">
            <form onSubmit={onSubmit} className="grid gap-4">
              <Field label="Organization name">
                <Input
                  required
                  autoFocus
                  maxLength={100}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Acme RL Environments"
                />
              </Field>
              {error && <ErrorBanner>{error}</ErrorBanner>}
              <Button type="submit" loading={busy} disabled={!name.trim()}>
                Create organization
              </Button>
            </form>
          </Card>
        </div>
      </main>
    </div>
  )
}
