import clsx from 'clsx'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { toneFill, verdictTone } from '../components/styles'
import { Button, ErrorBanner, Field, Input, Logo, ThemeToggle } from '../components/ui'
import { ApiError } from '../lib/api'
import { useAuth } from '../lib/auth'
import type { Verdict } from '../lib/types'

// Illustrative rows (LoopBench task names and their expected verdicts), shown as a sample report.
const SAMPLE_ROWS: [string, Verdict, number][] = [
  ['weak-output-check', 'exploitable', 50],
  ['bare-pytest-runner', 'exploitable', 0],
  ['broken-reference', 'broken', 65],
  ['flaky-reference', 'flaky', 85],
  ['hardened-word-count', 'robust', 100],
]

function SamplePanel() {
  return (
    <div className="relative hidden overflow-hidden bg-ink text-on-ink lg:flex lg:flex-col lg:justify-between">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 [background:radial-gradient(70%_55%_at_85%_100%,color-mix(in_srgb,var(--ember)_28%,transparent),transparent)]"
      />
      <div className="relative p-12 xl:p-16">
        <div className="label flex items-center gap-2 text-on-ink-muted">
          <span className="size-1.5 bg-ring rounded-full" aria-hidden /> Red-team your rewards
        </div>
        <p className="mt-6 max-w-md text-[30px] leading-[1.12] font-medium tracking-[-0.03em] xl:text-[36px]">
          If an agent can pass your verifier without doing the work, RL training will find out.{' '}
          <span className="text-on-ink-muted">RewardHacker finds out first.</span>
        </p>
      </div>

      <div className="relative px-12 pb-12 xl:px-16 xl:pb-16">
        <div className="overflow-hidden rounded-2xl border border-ink-border bg-ink-2">
          <div className="flex items-center justify-between border-b border-ink-border px-4 py-2.5">
            <span className="label text-on-ink-muted">Sample report · 5 tasks</span>
            <span className="font-mono text-[11px] text-on-ink-muted">rh bench</span>
          </div>
          <ul>
            {SAMPLE_ROWS.map(([task, verdict, score]) => (
              <li
                key={task}
                className="grid grid-cols-[minmax(0,1fr)_112px_40px] items-center gap-3 border-b border-ink-border px-4 py-2.5 last:border-0"
              >
                <span className="truncate font-mono text-[12px] text-on-ink">{task}</span>
                <span className="flex items-center gap-2 font-mono text-[10.5px] tracking-[0.06em] text-on-ink-muted uppercase">
                  <span aria-hidden className={clsx('size-2 rounded-full', toneFill[verdictTone[verdict]])} />
                  {verdict}
                </span>
                <span className="text-right font-mono text-[12px] text-on-ink tabular-nums">{score}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}

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
    <div className="grid min-h-dvh lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]">
      <div className="flex min-h-dvh flex-col">
        <header className="flex items-center justify-between px-5 py-5 sm:px-8">
          <Link to="/" aria-label="RewardHacker home">
            <Logo className="text-[15px]" />
          </Link>
          <ThemeToggle />
        </header>

        <main className="grid flex-1 place-items-center px-5 pb-16 sm:px-8">
          <div className="animate-in w-full max-w-[380px]">
            <div className="label flex items-center gap-2 text-accent-ink">
              <span className="size-1.5 bg-accent rounded-full" aria-hidden />
              {isLogin ? 'Sign in' : 'Create account'}
            </div>
            <h1 className="mt-4 text-[34px] leading-[1.05] font-semibold tracking-[-0.035em]">
              {isLogin ? 'Welcome back.' : 'Start red-teaming.'}
            </h1>
            <p className="mt-2.5 text-[15px] leading-relaxed text-muted">
              {isLogin ? 'Your tasks and reports are waiting.' : 'Probe your first RL task in a minute. Static probes are free.'}
            </p>

            <form onSubmit={onSubmit} className="mt-8 grid gap-5">
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

            <p className="mt-8 border-t border-border pt-6 text-[14px] text-muted">
              {isLogin ? 'New here? ' : 'Already have an account? '}
              <Link
                to={isLogin ? '/register' : '/login'}
                className="font-medium text-fg underline decoration-border-strong underline-offset-4 hover:decoration-accent"
              >
                {isLogin ? 'Create an account' : 'Sign in'}
              </Link>
            </p>
          </div>
        </main>
      </div>
      <SamplePanel />
    </div>
  )
}
