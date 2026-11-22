import { useQueryClient } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Button, ErrorBanner, Eyebrow, Field, Input, Logo, ThemeToggle } from '../components/ui'
import { api, ApiError } from '../lib/api'
import { useAuth } from '../lib/auth'

const ROLES: [string, string][] = [
  ['Admin', 'You. Manages members, keys and guidelines.'],
  ['Reviewer', 'Uploads tasks and starts runs.'],
  ['Viewer', 'Reads tasks, runs and reports.'],
]

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
    <div className="relative flex min-h-dvh flex-col">
      <div
        aria-hidden
        className="bg-graph pointer-events-none absolute inset-0 [mask-image:radial-gradient(70%_60%_at_50%_40%,black,transparent)]"
      />
      <header className="relative flex items-center justify-between px-5 py-5 sm:px-8">
        <Link to="/" aria-label="RewardHacker home">
          <Logo className="text-[15px]" />
        </Link>
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <Button variant="ghost" size="sm" onClick={logout}>
            Sign out
          </Button>
        </div>
      </header>
      <main className="relative grid flex-1 place-items-center px-5 pb-16 sm:px-8">
        <div className="animate-in w-full max-w-[460px]">
          {!first && (
            <Link to="/app" className="mb-6 inline-flex items-center gap-1.5 text-[13px] text-muted hover:text-fg">
              <ArrowLeft className="size-3.5" /> Back
            </Link>
          )}
          <Eyebrow>{first ? 'Get set up' : 'Organizations'}</Eyebrow>
          <h1 className="mt-4 text-[34px] leading-[1.05] font-semibold tracking-[-0.035em]">
            {first ? 'Create your first organization' : 'New organization'}
          </h1>
          <p className="mt-3 text-[15px] leading-relaxed text-muted">
            Tasks, runs and reports belong to an organization. You'll be its admin and can invite reviewers and viewers.
          </p>
          <div className="mt-8 overflow-hidden rounded-2xl border border-border bg-surface shadow-pop">
            <form onSubmit={onSubmit} className="grid gap-5 p-5 sm:p-6">
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
              <Button type="submit" size="lg" loading={busy} disabled={!name.trim()}>
                Create organization
              </Button>
            </form>
            <ul className="border-t border-border bg-bg px-5 py-4 sm:px-6">
              {ROLES.map(([role, help]) => (
                <li key={role} className="flex items-baseline gap-3 py-1 text-[13px]">
                  <span className="label w-20 shrink-0 text-fg">{role}</span>
                  <span className="text-muted">{help}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </main>
    </div>
  )
}
