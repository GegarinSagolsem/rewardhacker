import clsx from 'clsx'
import type { Severity, Verdict } from '../lib/types'

/* Non-component design helpers shared by ui.tsx and pages (kept apart for fast refresh). */

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'ink'
const buttonStyles: Record<ButtonVariant, string> = {
  primary: 'bg-accent text-accent-fg hover:bg-accent-hover',
  secondary: 'bg-surface text-fg border border-border-strong/80 hover:border-fg/40 hover:bg-surface-2/50',
  ghost: 'text-muted hover:text-fg hover:bg-surface-2',
  danger: 'bg-surface text-red border border-border-strong/80 hover:bg-red-soft hover:border-red/40',
  ink: 'bg-ink text-on-ink hover:bg-ink-2 border border-ink-border',
}

export const buttonClass = (variant: ButtonVariant = 'primary', size: 'sm' | 'md' | 'lg' = 'md', className?: string) =>
  clsx(
    'inline-flex items-center justify-center gap-2 rounded-full font-semibold whitespace-nowrap select-none',
    'transition-[background-color,border-color,color,transform] duration-150 active:translate-y-px',
    'disabled:pointer-events-none disabled:opacity-50',
    size === 'sm' && 'h-8 px-3.5 text-[13px] [&_svg]:size-3.5',
    size === 'md' && 'h-10 px-4.5 text-[13.5px] [&_svg]:size-4',
    size === 'lg' && 'h-[52px] px-6.5 text-[15px] [&_svg]:size-4',
    buttonStyles[variant],
    className,
  )

export type Tone = 'red' | 'orange' | 'yellow' | 'green' | 'gray' | 'blue' | 'accent' | 'neutral'

/** Solid fill per tone, for dots, bars and rules. */
export const toneFill: Record<Tone, string> = {
  red: 'bg-red-fill',
  orange: 'bg-orange-fill',
  yellow: 'bg-yellow-fill',
  green: 'bg-green-fill',
  gray: 'bg-gray-fill',
  blue: 'bg-blue-fill',
  accent: 'bg-accent',
  neutral: 'bg-subtle',
}
/** Text colour per tone. */
export const toneText: Record<Tone, string> = {
  red: 'text-red',
  orange: 'text-orange',
  yellow: 'text-yellow',
  green: 'text-green',
  gray: 'text-gray',
  blue: 'text-blue',
  accent: 'text-accent-ink',
  neutral: 'text-muted',
}

export const verdictTone: Record<Verdict, Tone> = {
  exploitable: 'red',
  broken: 'orange',
  flaky: 'yellow',
  robust: 'green',
  inconclusive: 'gray',
}

export const VERDICT_COPY: Record<Verdict, { title: string; line: string }> = {
  exploitable: { title: 'Exploitable', line: 'The reward can be earned without doing the task.' },
  broken: { title: 'Broken', line: "The task can't be solved as specified: the verifier rejects the reference solution." },
  flaky: { title: 'Flaky', line: 'The verifier gives different answers for the same work.' },
  robust: { title: 'Robust', line: 'None of the probes that ran found a way to earn the reward without doing the work.' },
  inconclusive: { title: 'Inconclusive', line: 'Some probes couldn’t run to completion, so the task can’t be called robust yet. Run it again.' },
}

export const severityTone: Record<Severity, Tone> = {
  critical: 'red',
  high: 'orange',
  medium: 'yellow',
  low: 'blue',
  info: 'gray',
}
