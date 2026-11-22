import clsx from 'clsx'
import { Bot, ChevronDown, Flag, Gavel } from 'lucide-react'
import { useState } from 'react'
import type { AgentRun, AgentStep } from '../lib/types'

const MAX_LINES = 8

function Output({ text }: { text: string }) {
  const [open, setOpen] = useState(false)
  const lines = text.replace(/\s+$/, '').split('\n')
  const long = lines.length > MAX_LINES
  const shown = open || !long ? lines : lines.slice(0, MAX_LINES)
  if (!text.trim()) return null
  return (
    <div className="border-t border-ink-border">
      <pre className="overflow-x-auto px-3.5 py-2.5 font-mono text-[11.5px] leading-relaxed whitespace-pre-wrap text-on-ink-muted">
        {shown.join('\n')}
      </pre>
      {long && (
        <button
          onClick={() => setOpen((v) => !v)}
          className="flex w-full items-center justify-center gap-1 border-t border-ink-border py-1.5 font-mono text-[11px] text-on-ink-muted hover:text-on-ink"
        >
          <ChevronDown className={clsx('size-3 transition-transform', open && 'rotate-180')} />
          {open ? 'Show less' : `Show ${lines.length - MAX_LINES} more lines`}
        </button>
      )}
    </div>
  )
}

function Step({ step, index }: { step: AgentStep; index: number }) {
  const command = typeof step.args?.command === 'string' ? step.args.command : null
  const explanation = typeof step.args?.explanation === 'string' ? step.args.explanation : null
  const submit = step.tool === 'submit'
  return (
    <li className="relative grid grid-cols-[24px_minmax(0,1fr)] gap-3.5">
      <span
        className={clsx(
          'z-10 mt-1 grid size-6 place-items-center rounded-lg border font-mono text-[10.5px] font-semibold',
          submit ? 'border-accent bg-accent text-accent-fg' : 'border-border-strong bg-surface text-muted',
        )}
      >
        {submit ? <Flag className="size-3" /> : String(index + 1).padStart(2, '0')}
      </span>
      <div className="min-w-0 pb-5">
        {step.text?.trim() && <p className="mb-2 text-[13.5px] leading-relaxed text-muted italic">“{step.text.trim()}”</p>}
        {step.tool === 'bash' && command != null && (
          <div className="overflow-hidden rounded-xl border border-ink-border bg-ink">
            <div className="flex items-center gap-1.5 border-b border-ink-border px-3.5 py-1.5">
              <span className="font-mono text-[10px] tracking-[0.08em] text-on-ink-muted uppercase">bash</span>
            </div>
            <pre className="overflow-x-auto px-3.5 py-2.5 font-mono text-[12px] leading-relaxed whitespace-pre-wrap text-on-ink">
              <span className="text-ring select-none">$ </span>
              {command}
            </pre>
            <Output text={step.output} />
          </div>
        )}
        {submit && (
          <div className="rounded-xl border border-border bg-surface-2/60 px-3.5 py-2.5 text-[13.5px] leading-relaxed">
            <span className="label mr-2 text-accent-ink">Submitted</span>
            {explanation}
          </div>
        )}
      </div>
    </li>
  )
}

export function TraceView({ agent, steps }: { agent: AgentRun; steps: AgentStep[] }) {
  const shortcut = agent.judgement === 'shortcut'
  return (
    <div>
      {steps.length > 0 ? (
        <ol className="relative before:absolute before:top-3 before:bottom-6 before:left-[11.5px] before:w-px before:bg-border-strong">
          {steps.map((s, i) => (
            <Step key={i} step={s} index={i} />
          ))}
        </ol>
      ) : (
        <p className="text-[13.5px] text-muted">
          <Bot className="mr-1 inline size-3.5" /> No steps recorded (stop reason: {agent.stop_reason}).
        </p>
      )}
      {agent.judgement && (
        <div
          className={clsx(
            'relative flex items-start gap-3 overflow-hidden rounded-xl border py-3 pr-3.5 pl-4 text-[13.5px] leading-relaxed',
            shortcut ? 'border-red/25 bg-red-soft' : 'border-border bg-surface-2/60',
          )}
        >
          <span aria-hidden className={clsx('absolute inset-y-0 left-0 w-[3px]', shortcut ? 'bg-red-fill' : 'bg-green-fill')} />
          <Gavel className={clsx('mt-0.5 size-4 shrink-0', shortcut ? 'text-red' : 'text-muted')} />
          <div>
            <span className={clsx('font-semibold', shortcut ? 'text-red' : 'text-fg')}>
              Judge:{' '}
              {agent.judgement === 'shortcut' ? 'shortcut' : agent.judgement === 'genuine' ? 'genuine solution' : 'unsure'}
            </span>
            {agent.judge_reason && <span className="text-muted"> · {agent.judge_reason}</span>}
          </div>
        </div>
      )}
    </div>
  )
}
