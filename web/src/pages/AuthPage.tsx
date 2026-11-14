import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Button, ErrorBanner, Field, Input, Logo, ThemeToggle } from '../components/ui'
import { ApiError } from '../lib/api'
import { useAuth } from '../lib/auth'

export default function AuthPage({ mode }: { mode: 'login' | 'register' }) {
  const { login, register } = useAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const isLogin = mode === 'login'

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await (isLogin ? login(email, password) : register(email, password))
      const next = params.get('next')
      navigate(next?.startsWith('/app') ? next : '/app', { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="relative flex min-h-dvh flex-col">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-72 bg-[radial-gradient(60%_100%_at_50%_0%,color-mix(in_srgb,var(--accent)_12%,transparent),transparent)]"
      />
      <header className="relative flex items-center justify-between px-4 py-4 sm:px-6">
        <Link to="/">
          <Logo className="text-[15px]" />
        </Link>
        <ThemeToggle />
      </header>

      <main className="relative grid flex-1 place-items-center px-4 pb-16">
        <div className="animate-in w-full max-w-[360px]">
          <h1 className="text-xl font-semibold tracking-tight">
            {isLogin ? 'Sign in to RewardHacker' : 'Create your account'}
          </h1>
          <p className="mt-1 text-[13px] text-muted">
            {isLogin ? 'Welcome back. Your tasks and reports are waiting.' : 'Start red-teaming your RL tasks in a minute.'}
          </p>

          <form onSubmit={onSubmit} className="mt-6 grid gap-4">
            <Field label="Email">
              <Input
                type="email"
                autoComplete="email"
                required
                autoFocus
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
              />
            </Field>
            <Field label="Password" hint={isLogin ? undefined : 'At least 8 characters.'}>
              <Input
                type="password"
                autoComplete={isLogin ? 'current-password' : 'new-password'}
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </Field>
            {error && <ErrorBanner>{error}</ErrorBanner>}
            <Button type="submit" size="lg" loading={busy} className="mt-1 w-full">
              {isLogin ? 'Sign in' : 'Create account'}
            </Button>
          </form>

          <p className="mt-6 text-center text-[13px] text-muted">
            {isLogin ? 'New here? ' : 'Already have an account? '}
            <Link
              to={isLogin ? '/register' : '/login'}
              className="font-medium text-fg underline decoration-border-strong underline-offset-4 hover:decoration-fg"
            >
              {isLogin ? 'Create an account' : 'Sign in'}
            </Link>
          </p>
        </div>
      </main>
    </div>
  )
}
