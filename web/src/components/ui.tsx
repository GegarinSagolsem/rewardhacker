import clsx from 'clsx'
import { AlertTriangle, ChevronDown, Info, Loader2, Monitor, Moon, Sun } from 'lucide-react'
import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from 'react'
import type { RunStatus, Severity, Verdict } from '../lib/types'
import { useTheme, type ThemePref } from '../lib/theme'
import { buttonClass, severityTone, toneFill, verdictTone, type ButtonVariant, type Tone } from './styles'

/* ---------- brand ---------- */

export function LogoMark({ className }: { className?: string }) {
  // A checkmark with a break in it: a pass that wasn't earned. The unearned half is the signal colour.
  return (
    <svg viewBox="0 0 32 32" className={clsx('shrink-0', className)} aria-hidden="true">
      <circle cx="16" cy="16" r="16" fill="var(--ink)" />
      <path d="M9 16.5l4.5 4.5" stroke="var(--on-ink)" strokeWidth="3.2" strokeLinecap="round" fill="none" />
      <path d="M16.9 17.6L23 11.5" stroke="var(--ember)" strokeWidth="3.2" strokeLinecap="round" fill="none" />
    </svg>
  )
}

export function Logo({ className }: { className?: string }) {
  return (
    <span className={clsx('inline-flex items-center gap-2.5 tracking-[-0.01em]', className)}>
      <LogoMark className="size-[1.6em]" />
      <span>
        <span className="font-bold">Reward</span>
        <span className="font-light">Hacker</span>
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


export function Button({
  variant = 'primary',
  size = 'md',
  loading,
  className,
  children,
  disabled,
  type = 'button',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
}) {
  return (
    <button {...props} type={type} disabled={disabled || loading} className={buttonClass(variant, size, className)}>
      {loading && <Loader2 className="animate-spin" />}
      {children}
    </button>
  )
}

const fieldBase =
  'w-full rounded-xl border border-border-strong/80 bg-surface px-3 text-[14px] text-fg ' +
  'placeholder:text-subtle transition-[border-color,box-shadow] hover:border-fg/35 ' +
  'focus:border-accent focus:outline-none focus:ring-3 focus:ring-accent/15 disabled:opacity-60'

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={clsx(fieldBase, 'h-10', className)} />
}

export function Textarea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={clsx(fieldBase, 'py-2.5 leading-relaxed', className)} />
}

/** Native select with a custom chevron. `className` sizes the control (e.g. `h-10 w-full sm:w-36`). */
export function Select({ className, children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <span className={clsx('relative inline-flex h-9 min-w-28', className)}>
      <select {...props} className={clsx(fieldBase, 'h-full appearance-none pr-8 text-[13.5px]')}>
        {children}
      </select>
      <ChevronDown className="pointer-events-none absolute top-1/2 right-2.5 size-3.5 -translate-y-1/2 text-muted" />
    </span>
  )
}

export function Field({ label, hint, children }: { label: string; hint?: ReactNode; children: ReactNode }) {
  return (
    <label className="grid gap-1.5">
      <span className="text-[13px] font-medium text-fg">{label}</span>
      {children}
      {hint && <span className="text-[12.5px] text-muted">{hint}</span>}
    </label>
  )
}

/** Segmented filter: a row of tabs that share one hairline frame. */
export function Segmented<T extends string | undefined>({
  options,
  value,
  onChange,
  label,
  className,
}: {
  options: [T, string][]
  value: T
  onChange: (v: T) => void
  label: string
  className?: string
}) {
  return (
    <div
      role="tablist"
      aria-label={label}
      className={clsx(
        'inline-flex max-w-full overflow-x-auto rounded-full border border-border bg-surface p-1 [scrollbar-width:none]',
        className,
      )}
    >
      {options.map(([v, text]) => (
        <button
          key={text}
          role="tab"
          aria-selected={value === v}
          onClick={() => onChange(v)}
          className={clsx(
            'h-8 shrink-0 rounded-full px-3.5 text-[12.5px] font-medium whitespace-nowrap transition-colors',
            value === v ? 'bg-ink text-on-ink' : 'text-muted hover:bg-surface-2 hover:text-fg',
          )}
        >
          {text}
        </button>
      ))}
    </div>
  )
}

/* ---------- surfaces ---------- */

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={clsx('rounded-2xl border border-border bg-surface shadow-card', className)}>{children}</div>
}

/** The header strip of a card: a mono label on the left, anything on the right. */
export function CardHeader({ title, aside, className }: { title: ReactNode; aside?: ReactNode; className?: string }) {
  return (
    <div
      className={clsx(
        'flex min-h-11 flex-wrap items-center gap-x-3 gap-y-1.5 border-b border-border px-4 py-2 sm:px-5',
        className,
      )}
    >
      <span className="label text-muted">{title}</span>
      {aside && <div className="ml-auto flex items-center gap-2 text-[12.5px] text-muted">{aside}</div>}
    </div>
  )
}

export function Eyebrow({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={clsx('label flex items-center gap-2 text-muted', className)}>
      <span className="size-1.5 bg-accent rounded-full" aria-hidden />
      {children}
    </div>
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
    <div className="mb-8 flex flex-wrap items-end justify-between gap-x-6 gap-y-4 border-b border-border pb-6">
      <div className="min-w-0">
        {eyebrow && <Eyebrow className="mb-3">{eyebrow}</Eyebrow>}
        <h1 className="text-[28px] leading-[1.1] font-semibold tracking-[-0.03em] sm:text-[34px]">{title}</h1>
        {description && <p className="mt-2.5 max-w-2xl text-[14.5px] leading-relaxed text-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

export function EmptyState({ icon, title, children }: { icon: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center px-6 py-16 text-center">
      <div className="mb-4 grid size-11 place-items-center rounded-xl border border-dashed border-border-strong bg-bg text-muted [&_svg]:size-4.5">
        {icon}
      </div>
      <div className="text-[15px] font-semibold tracking-tight">{title}</div>
      {children && <div className="mt-1.5 max-w-sm text-[13.5px] leading-relaxed text-muted">{children}</div>}
    </div>
  )
}

export function ErrorBanner({ children }: { children: ReactNode }) {
  return (
    <div
      role="alert"
      className="flex items-start gap-2.5 rounded-xl border border-red/25 bg-red-soft px-3.5 py-2.5 text-[13.5px] text-red"
    >
      <AlertTriangle className="mt-0.5 size-4 shrink-0" />
      <div className="min-w-0">{children}</div>
    </div>
  )
}

export function Notice({ children, icon, className }: { children: ReactNode; icon?: ReactNode; className?: string }) {
  return (
    <div
      className={clsx(
        'flex items-start gap-3 rounded-2xl border border-border bg-surface-2/60 px-4 py-3.5 text-[13.5px] leading-relaxed text-muted',
        className,
      )}
    >
      <span className="mt-0.5 shrink-0 text-fg [&_svg]:size-4">{icon ?? <Info />}</span>
      <div className="min-w-0">{children}</div>
    </div>
  )
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={clsx('size-4 animate-spin text-muted', className)} />
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-surface-2', className)} />
}

export function Mono({ children, className }: { children: ReactNode; className?: string }) {
  return <span className={clsx('font-mono text-[12.5px]', className)}>{children}</span>
}

/** A big number with a mono label: used for summary strips. */
export function Stat({
  label,
  children,
  className,
}: {
  label: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <div className={clsx('min-w-0', className)}>
      <div className="label text-muted">{label}</div>
      <div className="mt-2 truncate text-[22px] leading-none font-semibold tracking-[-0.02em] tabular-nums">
        {children}
      </div>
    </div>
  )
}

/* ---------- status language ---------- */


const toneStyles: Record<Tone, string> = {
  red: 'bg-red-soft text-red border-red/20',
  orange: 'bg-orange-soft text-orange border-orange/25',
  yellow: 'bg-yellow-soft text-yellow border-yellow/25',
  green: 'bg-green-soft text-green border-green/20',
  gray: 'bg-gray-soft text-gray border-gray/20',
  blue: 'bg-blue-soft text-blue border-blue/20',
  accent: 'bg-accent-soft text-accent-ink border-accent/25',
  neutral: 'bg-surface text-muted border-border-strong/70',
}

export function Badge({
  tone = 'neutral',
  dot,
  pulse,
  mono,
  children,
  className,
}: {
  tone?: Tone
  dot?: boolean
  pulse?: boolean
  /** Uppercase mono label style, used for verdicts and severities. */
  mono?: boolean
  children: ReactNode
  className?: string
}) {
  return (
    <span
      className={clsx(
        'inline-flex h-[22px] items-center gap-1.5 rounded-full border px-2.5 whitespace-nowrap',
        mono ? 'font-mono text-[10px] font-medium tracking-[0.06em] uppercase' : 'text-[12px] font-medium',
        toneStyles[tone],
        className,
      )}
    >
      {dot && (
        <span className="relative flex size-1.5">
          {pulse && <span className="absolute inline-flex size-full animate-ping rounded-full bg-current opacity-60" />}
          <span className={clsx('relative inline-flex size-1.5 rounded-full', toneFill[tone])} />
        </span>
      )}
      {children}
    </span>
  )
}



export function VerdictBadge({ verdict, className }: { verdict: Verdict | null; className?: string }) {
  if (!verdict) return <span className="text-subtle">—</span>
  return (
    <Badge tone={verdictTone[verdict]} dot mono className={className}>
      {verdict}
    </Badge>
  )
}

export function StatusBadge({ status }: { status: RunStatus }) {
  const map: Record<RunStatus, [Tone, string, boolean]> = {
    queued: ['gray', 'Queued', false],
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


export function SeverityBadge({ severity, className }: { severity: Severity; className?: string }) {
  return (
    <Badge tone={severityTone[severity]} mono className={className}>
      {severity}
    </Badge>
  )
}

/** Score out of 100 as a number plus a ten-tick gauge in the verdict colour. */
export function ScoreMeter({ score, verdict }: { score: number | null; verdict: Verdict | null }) {
  if (score == null) return <span className="text-subtle">—</span>
  const fill = toneFill[verdict ? verdictTone[verdict] : 'neutral']
  const on = Math.round(score / 10)
  return (
    <span className="inline-flex items-center gap-2.5" title={`Robustness score ${score}/100`}>
      <span className="w-6 text-right font-mono text-[12.5px] tabular-nums">{score}</span>
      <span className="flex gap-[2px]" aria-hidden>
        {Array.from({ length: 10 }, (_, i) => (
          <span key={i} className={clsx('h-3 w-[3px] rounded-full', i < on ? fill : 'bg-border')} />
        ))}
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
      className={clsx('inline-flex rounded-full border border-border bg-surface p-0.5', className)}
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
            'grid size-6 place-items-center rounded-full transition-colors',
            pref === value ? 'bg-ink text-on-ink' : 'text-muted hover:text-fg',
          )}
        >
          {icon}
        </button>
      ))}
    </div>
  )
}
