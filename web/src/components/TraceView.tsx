import clsx from 'clsx'
import { Bot, ChevronDown, Flag, Gavel, Terminal } from 'lucide-react'
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
    <div className="border-t border-white/5">
      <pre className="overflow-x-auto px-3 py-2 font-mono text-[11.5px] leading-relaxed whitespace-pre-wrap text-zinc-400">
        {shown.join('\n')}
      </pre>
      {long && (
        <button
          onClick={() => setOpen((v) => !v)}
          className="flex w-full items-center justify-center gap-1 border-t border-white/5 py-1 text-[11px] text-zinc-500 hover:text-zinc-300"
        >
          <ChevronDown className={clsx('size-3 transition-transform', open && 'rotate-180')} />
          {open ? 'Show less' : `Show ${lines.length - MAX_LINES} more lines`}
        </button>
      )}
    </div>
  )
}

function Step({ step }: { step: AgentStep }) {
  const command = typeof step.args?.command === 'string' ? step.args.command : null
  const explanation = typeof step.args?.explanation === 'string' ? step.args.explanation : null
  return (
    <li className="relative grid grid-cols-[20px_1fr] gap-3">
      <span className="z-10 mt-1.5 grid size-5 place-items-center rounded-full border border-border bg-surface text-muted">
        {step.tool === 'submit' ? <Flag className="size-2.5" /> : <Terminal className="size-2.5" />}
      </span>
      <div className="min-w-0 pb-4">
        {step.text?.trim() && <p className="mb-2 text-[13px] text-muted italic">“{step.text.trim()}”</p>}
        {step.tool === 'bash' && command != null && (
          <div className="overflow-hidden rounded-lg border border-zinc-800 bg-zinc-950 shadow-card">
            <pre className="overflow-x-auto px-3 py-2 font-mono text-[12px] leading-relaxed whitespace-pre-wrap text-zinc-100">
              <span className="text-violet-400 select-none">$ </span>
              {command}
            </pre>
            <Output text={step.output} />
          </div>
        )}
        {step.tool === 'submit' && (
          <div className="rounded-lg border border-border bg-surface-2 px-3 py-2 text-[13px]">
            <span className="text-xs font-medium text-muted">Agent submitted · </span>
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
        <ol className="relative before:absolute before:top-2 before:bottom-4 before:left-[9.5px] before:w-px before:bg-border">
          {steps.map((s, i) => (
            <Step key={i} step={s} />
          ))}
        </ol>
      ) : (
        <p className="text-[13px] text-muted">
          <Bot className="mr-1 inline size-3.5" /> No steps recorded (stop reason: {agent.stop_reason}).
        </p>
      )}
      {agent.judgement && (
        <div
          className={clsx(
            'flex items-start gap-2.5 rounded-lg border px-3 py-2.5 text-[13px]',
            shortcut ? 'border-red/25 bg-red-soft' : 'border-border bg-surface-2',
          )}
        >
          <Gavel className={clsx('mt-0.5 size-3.5 shrink-0', shortcut ? 'text-red' : 'text-muted')} />
          <div>
            <span className={clsx('font-medium', shortcut ? 'text-red' : 'text-fg')}>
              Judge: {agent.judgement === 'shortcut' ? 'shortcut' : agent.judgement === 'genuine' ? 'genuine solution' : 'unsure'}
            </span>
            {agent.judge_reason && <span className="text-muted"> · {agent.judge_reason}</span>}
          </div>
        </div>
      )}
    </div>
  )
}
