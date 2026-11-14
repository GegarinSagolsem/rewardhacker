import clsx from 'clsx'
import { AlertTriangle, Loader2, Monitor, Moon, Sun } from 'lucide-react'
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from 'react'
import type { RunStatus, Severity, Verdict } from '../lib/types'
import { useTheme, type ThemePref } from '../lib/theme'

/* ---------- brand ---------- */

export function LogoMark({ className }: { className?: string }) {
  // A checkmark with a break in it: a pass that wasn't earned.
  return (
    <svg viewBox="0 0 32 32" className={clsx('shrink-0', className)} aria-hidden="true">
      <rect width="32" height="32" rx="8" className="fill-accent" />
      <path d="M8.5 16.5l4.5 4.5" stroke="#fff" strokeWidth="3" strokeLinecap="round" fill="none" />
      <path d="M16.2 17.8L23.5 10.5" stroke="#fff" strokeWidth="3" strokeLinecap="round" fill="none" />
    </svg>
  )
}

export function Logo({ className }: { className?: string }) {
  return (
    <span className={clsx('inline-flex items-center gap-2 font-semibold tracking-tight', className)}>
      <LogoMark className="size-6" />
      <span>
        Reward<span className="text-accent">Hacker</span>
      </span>
    </span>
  )
}

export function GithubIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="currentColor" className={className} aria-hidden="true">
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
    </svg>
  )
}

/* ---------- controls ---------- */

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'
const buttonStyles: Record<ButtonVariant, string> = {
  primary: 'bg-accent text-accent-fg hover:bg-accent-hover shadow-card',
  secondary: 'bg-surface text-fg border border-border hover:bg-surface-2 hover:border-border-strong shadow-card',
  ghost: 'text-muted hover:text-fg hover:bg-surface-2',
  danger: 'bg-surface text-red border border-border hover:bg-red-soft hover:border-red/40',
}

export function Button({
  variant = 'primary',
  size = 'md',
  loading,
  className,
  children,
  disabled,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
}) {
  return (
    <button
      {...props}
      disabled={disabled || loading}
      className={clsx(
        'inline-flex items-center justify-center gap-1.5 rounded-lg font-medium whitespace-nowrap',
        'transition-[background-color,border-color,color,transform] duration-150 active:scale-[0.98]',
        'disabled:pointer-events-none disabled:opacity-50',
        size === 'sm' && 'h-7 px-2.5 text-xs',
        size === 'md' && 'h-8 px-3 text-[13px]',
        size === 'lg' && 'h-10 px-4 text-sm',
        buttonStyles[variant],
        className,
      )}
    >
      {loading && <Loader2 className="size-3.5 animate-spin" />}
      {children}
    </button>
  )
}

const fieldBase =
  'w-full rounded-lg border border-border bg-surface px-3 text-[13px] text-fg shadow-card ' +
  'placeholder:text-subtle transition-colors hover:border-border-strong ' +
  'focus:border-accent focus:outline-none focus:ring-3 focus:ring-accent/15'

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={clsx(fieldBase, 'h-9', className)} />
}

export function Select({ className, children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select {...props} className={clsx(fieldBase, 'h-8 w-auto pr-8', className)}>
      {children}
    </select>
  )
}

export function Field({ label, hint, children }: { label: string; hint?: ReactNode; children: ReactNode }) {
  return (
    <label className="grid gap-1.5">
      <span className="text-xs font-medium text-fg">{label}</span>
      {children}
      {hint && <span className="text-xs text-muted">{hint}</span>}
    </label>
  )
}

/* ---------- surfaces ---------- */

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div className={clsx('rounded-xl border border-border bg-surface shadow-card', className)}>{children}</div>
  )
}

export function PageHeader({
  title,
  description,
  actions,
  eyebrow,
}: {
  title: ReactNode
  description?: ReactNode
  actions?: ReactNode
  eyebrow?: ReactNode
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {eyebrow && <div className="mb-1.5 text-xs text-muted">{eyebrow}</div>}
        <h1 className="text-xl font-semibold tracking-tight text-balance">{title}</h1>
        {description && <p className="mt-1 max-w-2xl text-[13px] text-muted">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  )
}

export function EmptyState({ icon, title, children }: { icon: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center px-6 py-14 text-center">
      <div className="mb-3 grid size-10 place-items-center rounded-xl border border-border bg-surface-2 text-muted">
        {icon}
      </div>
      <div className="font-medium">{title}</div>
      {children && <div className="mt-1 max-w-sm text-[13px] text-muted">{children}</div>}
    </div>
  )
}

export function ErrorBanner({ children }: { children: ReactNode }) {
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-lg border border-red/25 bg-red-soft px-3 py-2 text-[13px] text-red"
    >
      <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
      <div className="min-w-0">{children}</div>
    </div>
  )
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={clsx('size-4 animate-spin text-muted', className)} />
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded-md bg-surface-2', className)} />
}

export function Mono({ children, className }: { children: ReactNode; className?: string }) {
  return <span className={clsx('font-mono text-[12px]', className)}>{children}</span>
}

/* ---------- status language ---------- */

type Tone = 'red' | 'orange' | 'amber' | 'green' | 'blue' | 'neutral' | 'accent'
const toneStyles: Record<Tone, string> = {
  red: 'bg-red-soft text-red border-red/20',
  orange: 'bg-orange-soft text-orange border-orange/20',
  amber: 'bg-amber-soft text-amber border-amber/20',
  green: 'bg-green-soft text-green border-green/20',
  blue: 'bg-blue-soft text-blue border-blue/20',
  accent: 'bg-accent-soft text-accent border-accent/20',
  neutral: 'bg-surface-2 text-muted border-border',
}

export function Badge({
  tone = 'neutral',
  dot,
  pulse,
  children,
  className,
}: {
  tone?: Tone
  dot?: boolean
  pulse?: boolean
  children: ReactNode
  className?: string
}) {
  return (
    <span
      className={clsx(
        'inline-flex h-5 items-center gap-1.5 rounded-md border px-1.5 text-[11px] font-medium whitespace-nowrap',
        toneStyles[tone],
        className,
      )}
    >
      {dot && (
        <span className="relative flex size-1.5">
          {pulse && <span className="absolute inline-flex size-full animate-ping rounded-full bg-current opacity-60" />}
          <span className="relative inline-flex size-1.5 rounded-full bg-current" />
        </span>
      )}
      {children}
    </span>
  )
}

export const verdictTone: Record<Verdict, Tone> = {
  exploitable: 'red',
  broken: 'orange',
  flaky: 'amber',
  robust: 'green',
  inconclusive: 'neutral',
}

export function VerdictBadge({ verdict, className }: { verdict: Verdict | null; className?: string }) {
  if (!verdict) return <span className="text-subtle">—</span>
  return (
    <Badge tone={verdictTone[verdict]} dot className={clsx('uppercase tracking-wide', className)}>
      {verdict}
    </Badge>
  )
}

export function StatusBadge({ status }: { status: RunStatus }) {
  const map: Record<RunStatus, [Tone, string, boolean]> = {
    queued: ['neutral', 'Queued', false],
    running: ['blue', 'Running', true],
    done: ['neutral', 'Done', false],
    failed: ['red', 'Failed', false],
  }
  const [tone, label, pulse] = map[status]
  return (
    <Badge tone={tone} dot pulse={pulse}>
      {label}
    </Badge>
  )
}

export const severityTone: Record<Severity, Tone> = {
  critical: 'red',
  high: 'orange',
  medium: 'amber',
  low: 'blue',
  info: 'neutral',
}

export function SeverityBadge({ severity, className }: { severity: Severity; className?: string }) {
  return (
    <Badge tone={severityTone[severity]} className={clsx('uppercase tracking-wide', className)}>
      {severity}
    </Badge>
  )
}

export function ScoreMeter({ score, verdict }: { score: number | null; verdict: Verdict | null }) {
  if (score == null) return <span className="text-subtle">—</span>
  const tone = verdict ? verdictTone[verdict] : 'neutral'
  const bar = { red: 'bg-red', orange: 'bg-orange', amber: 'bg-amber', green: 'bg-green' }[tone as string] ?? 'bg-subtle'
  return (
    <span className="inline-flex items-center gap-2">
      <span className="font-mono text-[12px] tabular-nums">{score}</span>
      <span className="h-1 w-12 overflow-hidden rounded-full bg-surface-2">
        <span className={clsx('block h-full rounded-full', bar)} style={{ width: `${score}%` }} />
      </span>
    </span>
  )
}

/* ---------- theme ---------- */

export function ThemeToggle({ className }: { className?: string }) {
  const { pref, set } = useTheme()
  const options: [ThemePref, ReactNode, string][] = [
    ['light', <Sun key="l" className="size-3.5" />, 'Light theme'],
    ['system', <Monitor key="s" className="size-3.5" />, 'System theme'],
    ['dark', <Moon key="d" className="size-3.5" />, 'Dark theme'],
  ]
  return (
    <div
      role="radiogroup"
      aria-label="Theme"
      className={clsx('inline-flex rounded-lg border border-border bg-surface-2 p-0.5', className)}
    >
      {options.map(([value, icon, label]) => (
        <button
          key={value}
          role="radio"
          aria-checked={pref === value}
          aria-label={label}
          title={label}
          onClick={() => set(value)}
          className={clsx(
            'grid size-6 place-items-center rounded-md transition-colors',
            pref === value ? 'bg-surface text-fg shadow-card' : 'text-muted hover:text-fg',
          )}
        >
          {icon}
        </button>
      ))}
    </div>
  )
}
