import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { BookOpenText, ChevronDown, ScanSearch, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { timeAgo, usd } from '../lib/format'
import type { SpecCheck } from '../lib/types'
import { severityTone, toneFill } from './styles'
import { Button, Card, CardHeader, ErrorBanner, SeverityBadge, Skeleton } from './ui'

const RANK = { high: 0, medium: 1, low: 2 } as const

function Result({ check }: { check: SpecCheck }) {
  const [showExcerpts, setShowExcerpts] = useState(false)
  const { summary, issues, excerpts } = check.result
  return (
    <div>
      {summary && <p className="px-4 pt-4 text-[14px] leading-relaxed sm:px-5">{summary}</p>}
      {issues.length === 0 ? (
        <div className="flex items-center gap-2 px-4 py-4 text-[13.5px] text-muted sm:px-5">
          <ShieldCheck className="size-4 text-green" /> No guideline problems found.
        </div>
      ) : (
        <ul className="grid gap-2.5 p-4 sm:px-5">
          {[...issues]
            .sort((a, b) => RANK[a.severity] - RANK[b.severity])
            .map((i, n) => (
              <li key={n} className="relative overflow-hidden rounded-xl border border-border bg-surface">
                <span aria-hidden className={clsx('absolute inset-y-0 left-0 w-[3px]', toneFill[severityTone[i.severity]])} />
                <div className="flex flex-wrap items-start gap-2.5 py-3 pr-3.5 pl-4">
                  <SeverityBadge severity={i.severity} />
                  <span className="min-w-0 flex-1 text-[13.5px] leading-relaxed">{i.issue}</span>
                </div>
                {i.suggestion && (
                  <div className="flex gap-3 border-t border-border bg-bg py-2.5 pr-3.5 pl-4 text-[13px] leading-relaxed">
                    <span className="label mt-[3px] shrink-0 text-accent-ink">Fix</span>
                    <span className="text-muted">{i.suggestion}</span>
                  </div>
                )}
                {i.heading && (
                  <div className="flex items-center gap-1.5 border-t border-border py-2 pr-3.5 pl-4 text-[12px] text-subtle">
                    <BookOpenText className="size-3" />
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
            className="flex w-full items-center gap-1.5 px-4 py-2.5 text-[12.5px] text-muted hover:text-fg sm:px-5"
            aria-expanded={showExcerpts}
          >
            <ChevronDown className={clsx('size-3.5 transition-transform', showExcerpts && 'rotate-180')} />
            {excerpts.length} guideline excerpts retrieved
          </button>
          {showExcerpts && (
            <ol className="grid gap-2 px-4 pb-4 sm:px-5">
              {excerpts.map((e) => (
                <li key={e.n} className="rounded-xl border border-border bg-bg px-3.5 py-2.5">
                  <div className="label text-muted">
                    [{e.n}] {e.heading || e.title}
                  </div>
                  <p className="mt-1.5 line-clamp-4 text-[12.5px] leading-relaxed whitespace-pre-wrap text-muted">{e.text}</p>
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
      <CardHeader
        title="Guideline check"
        aside={
          <>
            {latest && (
              <span className="hidden text-[12px] text-subtle sm:inline">
                {timeAgo(latest.created_at)} · {latest.created_by_label} · {usd(latest.cost_usd)}
              </span>
            )}
            {canRun && (
              <Button size="sm" variant="secondary" onClick={() => run.mutate()} loading={run.isPending}>
                {!run.isPending && <ScanSearch />} {latest ? 'Check again' : 'Check against guidelines'}
              </Button>
            )}
          </>
        }
      />
      {run.error && (
        <div className="px-4 pt-4 sm:px-5">
          <ErrorBanner>{run.error.message}</ErrorBanner>
        </div>
      )}
      {checks.isPending ? (
        <div className="p-4 sm:p-5">
          <Skeleton className="h-12" />
        </div>
      ) : latest ? (
        <Result check={latest} />
      ) : (
        <p className="px-4 py-5 text-[14px] leading-relaxed text-muted sm:px-5">
          Compare this task with your team's{' '}
          <Link to={`/app/${orgId}/guidelines`} className="text-fg underline decoration-border-strong underline-offset-4 hover:decoration-accent">
            guidelines
          </Link>
          . Finds problems the probes can't see, like hidden requirements or tests that can be hard-coded. About
          $0.001.
        </p>
      )}
    </Card>
  )
}
