import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BookOpenText, ChevronDown, ScanSearch, ShieldCheck, Wrench } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { timeAgo, usd } from '../lib/format'
import type { SpecCheck } from '../lib/types'
import { Button, Card, ErrorBanner, SeverityBadge, Skeleton } from './ui'

const RANK = { high: 0, medium: 1, low: 2 } as const

function Result({ check }: { check: SpecCheck }) {
  const [showExcerpts, setShowExcerpts] = useState(false)
  const { summary, issues, excerpts } = check.result
  return (
    <div>
      {summary && <p className="px-4 pt-3 text-[13px]">{summary}</p>}
      {issues.length === 0 ? (
        <div className="flex items-center gap-2 px-4 py-3 text-[13px] text-muted">
          <ShieldCheck className="size-4 text-green" /> No guideline problems found.
        </div>
      ) : (
        <ul className="grid gap-2 p-4">
          {[...issues].sort((a, b) => RANK[a.severity] - RANK[b.severity]).map((i, n) => (
            <li key={n} className="rounded-lg border border-border">
              <div className="flex flex-wrap items-start gap-2 px-3 pt-2.5">
                <SeverityBadge severity={i.severity} />
                <span className="min-w-0 flex-1 text-[13px]">{i.issue}</span>
              </div>
              {i.suggestion && (
                <div className="mt-2 flex gap-2 border-t border-border bg-surface-2/50 px-3 py-2 text-xs">
                  <Wrench className="mt-0.5 size-3 shrink-0 text-accent" />
                  <span className="text-muted">{i.suggestion}</span>
                </div>
              )}
              {i.heading && (
                <div className="border-t border-border px-3 py-1.5 text-[11px] text-subtle">
                  <BookOpenText className="mr-1 inline size-3" />
                  {i.heading}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
      {excerpts.length > 0 && (
        <div className="border-t border-border">
          <button
            onClick={() => setShowExcerpts((v) => !v)}
            className="flex w-full items-center gap-1.5 px-4 py-2 text-xs text-muted hover:text-fg"
            aria-expanded={showExcerpts}
          >
            <ChevronDown className={`size-3 transition-transform ${showExcerpts ? 'rotate-180' : ''}`} />
            {excerpts.length} guideline excerpts retrieved
          </button>
          {showExcerpts && (
            <ol className="grid gap-2 px-4 pb-4">
              {excerpts.map((e) => (
                <li key={e.n} className="rounded-lg bg-surface-2/60 px-3 py-2">
                  <div className="text-[11px] font-medium text-muted">
                    [{e.n}] {e.heading || e.title}
                  </div>
                  <p className="mt-1 line-clamp-4 text-xs whitespace-pre-wrap text-muted">{e.text}</p>
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
    </div>
  )
}

export function SpecCheckPanel({ orgId, taskId, canRun }: { orgId: string; taskId: string; canRun: boolean }) {
  const qc = useQueryClient()
  const checks = useQuery({ queryKey: ['spec-checks', orgId, taskId], queryFn: () => api.specChecks(orgId, taskId) })
  const run = useMutation({
    mutationFn: () => api.runSpecCheck(orgId, taskId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['spec-checks', orgId, taskId] }),
  })
  const latest = checks.data?.[0]

  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-2.5">
        <span className="text-xs font-medium text-muted">Guideline check</span>
        {latest && (
          <span className="text-[11px] text-subtle">
            · {timeAgo(latest.created_at)} by {latest.created_by_label} · {usd(latest.cost_usd)}
          </span>
        )}
        {canRun && (
          <Button size="sm" variant="secondary" className="ml-auto" onClick={() => run.mutate()} loading={run.isPending}>
            <ScanSearch className="size-3.5" /> {latest ? 'Check again' : 'Check against guidelines'}
          </Button>
        )}
      </div>
      {run.error && (
        <div className="p-4 pb-0">
          <ErrorBanner>{run.error.message}</ErrorBanner>
        </div>
      )}
      {checks.isPending ? (
        <div className="p-4">
          <Skeleton className="h-12" />
        </div>
      ) : latest ? (
        <Result check={latest} />
      ) : (
        <p className="px-4 py-4 text-[13px] text-muted">
          Compare this task with your team's{' '}
          <Link to={`/app/${orgId}/guidelines`} className="text-fg underline decoration-border-strong underline-offset-4">
            guidelines
          </Link>
          . Finds problems the probes can't see, like hidden requirements or tests that can be hard-coded. About
          $0.001.
        </p>
      )}
    </Card>
  )
}
