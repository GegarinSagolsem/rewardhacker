import { useMutation, useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { ArrowLeft, CheckCircle2, Clock, Download, Loader2, ShieldCheck, Sparkles, TriangleAlert } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Menu } from '../components/Menu'
import { TD, TH, THEAD_ROW } from '../components/RunsTable'
import { TraceView } from '../components/TraceView'
import { severityTone, toneFill, toneText, VERDICT_COPY, verdictTone, type Tone } from '../components/styles'
import { Badge, Button, Card, ErrorBanner, Mono, SeverityBadge, Skeleton, StatusBadge } from '../components/ui'
import { api, downloadExport } from '../lib/api'
import { atLeast } from '../lib/auth'
import { shortId, timeAgo, usd } from '../lib/format'
import { useOrg } from '../lib/org'
import type { ExportKind, Finding, ProbeResult, Report, RunDetail as RunDetailT, TraceDoc } from '../lib/types'

function Section({ title, aside, children }: { title: string; aside?: ReactNode; children: ReactNode }) {
  return (
    <section className="mt-12">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b border-border pb-3">
        <h2 className="text-[19px] font-semibold tracking-[-0.02em]">{title}</h2>
        {aside && <div className="label text-muted">{aside}</div>}
      </div>
      {children}
    </section>
  )
}

function FindingCard({ f }: { f: Finding }) {
  return (
    <Card className="relative overflow-hidden">
      <span aria-hidden className={clsx('absolute inset-y-0 left-0 w-[3px]', toneFill[severityTone[f.severity]])} />
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 pt-4 pr-4 pl-5 sm:pr-5 sm:pl-6">
        <SeverityBadge severity={f.severity} />
        <h3 className="min-w-0 text-[15px] font-semibold tracking-[-0.01em]">{f.title}</h3>
        <Mono className="ml-auto text-[11.5px] text-subtle">{f.code}</Mono>
      </div>
      <p className="max-w-[80ch] pt-2.5 pr-4 pb-4 pl-5 text-[14px] leading-relaxed whitespace-pre-wrap text-muted sm:pr-5 sm:pl-6">
        {f.detail}
      </p>
      {f.recommendation && (
        <div className="flex gap-4 border-t border-border bg-bg py-3.5 pr-4 pl-5 text-[13.5px] leading-relaxed sm:pr-5 sm:pl-6">
          <span className="label mt-[3px] shrink-0 text-accent-ink">How to fix</span>
          <span className="text-fg/85">{f.recommendation}</span>
        </div>
      )}
    </Card>
  )
}

function probeOutcome(p: ProbeResult): [string, Tone] {
  if (p.status === 'finding') return ['Loophole', 'red']
  if (p.status === 'error') return ['Error', 'yellow']
  if (p.status === 'skipped') return ['Skipped', 'gray']
  return [p.expect_pass ? 'Passed' : 'Held', 'green']
}

/** One cell per probe: the shape of the run in a single glance. */
function ProbeStrip({ probes }: { probes: ProbeResult[] }) {
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-surface">
      <ul className="-mr-px -mb-px grid grid-cols-2 sm:grid-cols-3">
        {probes.map((p) => {
          const [label, tone] = probeOutcome(p)
          return (
            <li key={p.name} className="min-w-0 border-r border-b border-border px-3 py-2.5" title={`${p.name}: ${label}`}>
              <div className="truncate font-mono text-[11.5px] text-fg">{p.name}</div>
              <div className={clsx('mt-1 flex items-center gap-1.5 text-[12px] font-medium', toneText[tone])}>
                <span aria-hidden className={clsx('size-1.5 shrink-0 rounded-full', toneFill[tone])} />
                {label}
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

function ProbesTable({ probes }: { probes: ProbeResult[] }) {
  return (
    <Card className="overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-[13.5px]">
          <thead>
            <tr className={THEAD_ROW}>
              <th className={TH}>Probe</th>
              <th className={TH}>Result</th>
              <th className={`${TH} hidden sm:table-cell`}>Verifier passed</th>
              <th className={`${TH} hidden md:table-cell`}>Note</th>
            </tr>
          </thead>
          <tbody>
            {probes.map((p) => {
              const ran = p.trials.filter((t) => t.passed !== null)
              const passed = ran.filter((t) => t.passed).length
              const [label, tone] = probeOutcome(p)
              return (
                <tr key={p.name} className="border-b border-border last:border-0">
                  <td className={TD}>
                    <div className="font-mono text-[12.5px] font-medium">{p.name}</div>
                    <div className="mt-0.5 text-[12.5px] text-muted">{p.title}</div>
                  </td>
                  <td className={TD}>
                    <Badge tone={tone} dot>
                      {label}
                    </Badge>
                  </td>
                  <td className={`${TD} hidden whitespace-nowrap sm:table-cell`}>
                    <Mono className="text-fg">{ran.length ? `${passed}/${ran.length}` : '—'}</Mono>
                    <span className="ml-2 text-[12px] text-subtle">{p.expect_pass ? 'should pass' : 'should fail'}</span>
                  </td>
                  <td
                    className={`${TD} hidden max-w-[300px] truncate text-[12.5px] text-muted md:table-cell`}
                    title={p.note ?? ''}
                  >
                    {p.note ?? ''}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

function AdversarySection({ report, traces }: { report: Report; traces: TraceDoc[] | undefined }) {
  const trials = report.probes.flatMap((p) =>
    p.trials.filter((t) => t.agent).map((t) => ({ probe: p.name, trial: t, agent: t.agent! })),
  )
  if (!trials.length) return null
  return (
    <Section
      title="Adversary replay"
      aside={
        report.llm_usage && (
          <>
            {report.llm_usage.model} · {report.llm_usage.calls} calls · {usd(report.llm_usage.cost_usd)}
          </>
        )
      }
    >
      <div className="grid gap-4">
        {trials.map(({ probe, trial, agent }) => {
          const doc = traces?.find((d) => d.probe === probe && d.trial === trial.index)
          const steps = doc?.steps ?? agent.steps
          return (
            <Card key={`${probe}-${trial.index}`} className="p-4 sm:p-6">
              <div className="mb-5 flex flex-wrap items-center gap-2.5">
                <span className="grid size-7 place-items-center rounded-xl bg-accent-soft text-accent-ink">
                  <Sparkles className="size-3.5" />
                </span>
                <span className="text-[14px] font-medium">LLM agent told to earn the reward without doing the task</span>
                <Badge tone={trial.passed ? 'red' : 'green'} mono dot className="ml-auto">
                  verifier {trial.passed ? 'passed' : 'failed'}
                </Badge>
              </div>
              <TraceView agent={agent} steps={steps} />
            </Card>
          )
        })}
      </div>
    </Section>
  )
}

function DownloadReport({ orgId, runId }: { orgId: string; runId: string }) {
  const dl = useMutation({ mutationFn: (kind: ExportKind) => downloadExport(orgId, kind, runId) })
  return (
    <div className="grid justify-items-start gap-1">
      <Menu
        align="left"
        trigger={({ toggle, open }) => (
          <Button variant="secondary" onClick={toggle} aria-expanded={open} loading={dl.isPending}>
            {!dl.isPending && <Download />} Download report
          </Button>
        )}
        items={[
          { label: 'Markdown', hint: 'Readable; paste into a ticket or PR', onSelect: () => dl.mutate('report.md') },
          { label: 'JSON', hint: 'Full report with adversary traces', onSelect: () => dl.mutate('report.json') },
        ]}
      />
      {dl.error && <span className="text-[12.5px] text-red">{dl.error.message}</span>}
    </div>
  )
}

function StatRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-t border-border py-3 first:border-t-0">
      <span className="label text-muted">{label}</span>
      <span className="truncate text-[14px] font-medium tabular-nums">{children}</span>
    </div>
  )
}

function VerdictHero({ run, report, orgId, canDownload }: { run: RunDetailT; report: Report; orgId: string; canDownload: boolean }) {
  const verdict = report.verdict
  const tone = verdictTone[verdict]
  const counted = report.probes.filter((p) => p.status === 'ok' || p.status === 'finding')
  const on = Math.round(report.score / 10)
  const scored = verdict !== 'inconclusive'
  return (
    <Card className="relative overflow-hidden lg:grid lg:grid-cols-[minmax(0,1fr)_300px]">
      <span aria-hidden className={clsx('absolute inset-x-0 top-0 h-1', toneFill[tone])} />
      <div className="min-w-0 p-5 pt-7 sm:p-8 sm:pt-9">
        <div className="label text-muted">Verdict</div>
        <h1
          className={clsx(
            'mt-3 flex items-center gap-4 text-[44px] leading-[0.95] font-semibold tracking-[-0.045em] sm:text-[64px]',
            toneText[tone],
          )}
        >
          <span aria-hidden className={clsx('size-3 shrink-0 rounded-full sm:size-4', toneFill[tone])} />
          {VERDICT_COPY[verdict].title}
        </h1>
        <p className="mt-4 max-w-xl text-[15.5px] leading-relaxed text-muted">{VERDICT_COPY[verdict].line}</p>
        {canDownload && (
          <div className="mt-6">
            <DownloadReport orgId={orgId} runId={run.id} />
          </div>
        )}
        <div className="mt-8">
          <div className="label mb-2.5 text-muted">Probe results</div>
          <ProbeStrip probes={report.probes} />
        </div>
      </div>
      <aside className="border-t border-border bg-bg/70 p-5 sm:p-8 lg:border-t-0 lg:border-l">
        <div className="label text-muted">Robustness score</div>
        {scored ? (
          <>
            <div className="mt-3 flex items-baseline gap-1.5">
              <span className={clsx('text-[64px] leading-[0.9] font-semibold tracking-[-0.05em] tabular-nums', toneText[tone])}>
                {report.score}
              </span>
              <span className="text-[18px] font-medium text-subtle">/100</span>
            </div>
            <div className="mt-4 flex gap-1" aria-hidden>
              {Array.from({ length: 10 }, (_, i) => (
                <span key={i} className={clsx('h-2 flex-1 rounded-full', i < on ? toneFill[tone] : 'bg-border')} />
              ))}
            </div>
          </>
        ) : (
          <>
            <div className="mt-3 text-[64px] leading-[0.9] font-semibold tracking-[-0.05em] text-subtle">—</div>
            <p className="mt-4 text-[13px] leading-relaxed text-muted">Not scored: at least one probe couldn’t run to completion.</p>
          </>
        )}
        <div className="mt-6">
          <StatRow label="Probes ran">
            {counted.length}
            <span className="text-subtle">/{report.probes.length}</span>
          </StatRow>
          <StatRow label="Findings">{report.findings.length}</StatRow>
          <StatRow label="Duration">{report.duration_sec.toFixed(1)}s</StatRow>
          <StatRow label="LLM cost">
            {run.include_llm ? usd(run.llm_cost_usd ?? 0) : <span className="text-subtle">not used</span>}
          </StatRow>
        </div>
      </aside>
    </Card>
  )
}

function Pending({ run }: { run: RunDetailT }) {
  const running = run.status === 'running'
  return (
    <Card className="relative overflow-hidden p-6 sm:p-8">
      <span aria-hidden className={clsx('absolute inset-x-0 top-0 h-1', running ? 'bg-blue-fill' : 'bg-gray-fill')} />
      <div className="flex items-start gap-4">
        <span className="grid size-10 shrink-0 place-items-center rounded-xl border border-border bg-bg">
          {running ? <Loader2 className="size-4.5 animate-spin text-blue" /> : <Clock className="size-4.5 text-muted" />}
        </span>
        <div>
          <div className="text-[16px] font-semibold tracking-tight">{running ? 'Probing in Docker…' : 'Waiting for a worker'}</div>
          <p className="mt-1.5 max-w-xl text-[14px] leading-relaxed text-muted">
            {running
              ? `Started ${timeAgo(run.started_at)}. Static probes take about a minute; the adversary adds ~30s. This page updates on its own.`
              : 'The run is queued. Start a worker with '}
            {!running && <Mono className="rounded-full border border-border bg-surface-2 px-1.5 py-0.5 text-fg">uv run rh worker</Mono>}
            {!running && ' and it will be picked up.'}
          </p>
        </div>
      </div>
    </Card>
  )
}

export default function RunDetail() {
  const org = useOrg()
  const { runId = '' } = useParams()
  const run = useQuery({
    queryKey: ['run', org.id, runId],
    queryFn: () => api.run(org.id, runId),
    refetchInterval: (q) => (q.state.data && ['queued', 'running'].includes(q.state.data.status) ? 2500 : false),
  })
  const task = useQuery({
    queryKey: ['task', org.id, run.data?.task_id],
    queryFn: () => api.task(org.id, run.data!.task_id),
    enabled: !!run.data,
  })
  const traces = useQuery({
    queryKey: ['traces', org.id, runId],
    queryFn: () => api.traces(org.id, runId),
    enabled: !!run.data?.traces_stored,
  })

  if (run.error) return <ErrorBanner>{run.error.message}</ErrorBanner>
  const r = run.data
  const report = r?.report ?? null
  const verdict = report?.verdict ?? null

  return (
    <div className="animate-in">
      <Link to={`/app/${org.id}/runs`} className="mb-5 inline-flex items-center gap-1.5 text-[13px] text-muted hover:text-fg">
        <ArrowLeft className="size-3.5" /> All runs
      </Link>

      {!r ? (
        <div className="grid gap-3">
          <Skeleton className="h-4 w-48" />
          <Skeleton className="h-64" />
        </div>
      ) : (
        <>
          <div className="mb-4 flex flex-wrap items-center gap-x-2.5 gap-y-1.5 text-[13px] text-muted">
            <span className="label">Run</span>
            <Mono className="text-fg">{shortId(r.id)}</Mono>
            <span className="text-border-strong">/</span>
            <span className="label">Task</span>
            <Link
              to={`/app/${org.id}/tasks/${r.task_id}`}
              className="font-mono text-[12.5px] text-fg underline decoration-border-strong underline-offset-4 hover:decoration-accent"
            >
              {task.data?.spec_id ?? shortId(r.task_id)}
            </Link>
            <span className="text-border-strong">/</span>
            <span>{timeAgo(r.created_at)}</span>
            {r.include_llm && (
              <Badge tone="accent" className="ml-1">
                <Sparkles className="size-3" /> adversary
              </Badge>
            )}
            {r.status !== 'done' && <StatusBadge status={r.status} />}
          </div>

          {r.status === 'done' && verdict && report ? (
            <>
              <VerdictHero run={r} report={report} orgId={org.id} canDownload={atLeast(org.role, 'reviewer')} />

              <Section title="Findings" aside={report.findings.length ? `${report.findings.length} total` : undefined}>
                {report.findings.length ? (
                  <div className="grid gap-3">
                    {report.findings.map((f, i) => (
                      <FindingCard key={`${f.code}-${i}`} f={f} />
                    ))}
                  </div>
                ) : (
                  <Card className="flex flex-wrap items-center gap-3 p-5">
                    <ShieldCheck className="size-5 text-green" />
                    <span className="text-[14.5px] font-medium">No loopholes found.</span>
                    {!r.include_llm && (
                      <span className="text-[13px] text-muted">
                        Static probes only. Add the LLM adversary to look for task-specific shortcuts.
                      </span>
                    )}
                  </Card>
                )}
              </Section>

              <AdversarySection report={report} traces={traces.data} />

              <Section
                title="Probes"
                aside={
                  <span className="inline-flex items-center gap-1.5">
                    <CheckCircle2 className="size-3" />
                    rewardhacker {report.rewardhacker_version}
                  </span>
                }
              >
                <ProbesTable probes={report.probes} />
              </Section>
            </>
          ) : r.status === 'failed' ? (
            <>
              <h1 className="flex items-center gap-3 text-[34px] leading-tight font-semibold tracking-[-0.03em] text-red">
                <TriangleAlert className="size-7" /> Run failed
              </h1>
              <p className="mt-2 mb-6 max-w-xl text-[15px] text-muted">
                The task could not be probed. This usually means the environment failed to build.
              </p>
              <div className="overflow-hidden rounded-2xl border border-ink-border bg-ink">
                <div className="label flex items-center gap-2 border-b border-ink-border px-4 py-2.5 text-on-ink-muted">
                  <span className="size-1.5 bg-red-fill rounded-full" aria-hidden /> Error
                </div>
                <pre className="overflow-x-auto p-4 font-mono text-[12.5px] leading-relaxed whitespace-pre-wrap text-on-ink">
                  {r.error}
                </pre>
              </div>
            </>
          ) : (
            <>
              <h1 className="mb-6 text-[34px] leading-tight font-semibold tracking-[-0.03em]">
                {r.status === 'running' ? 'Running' : 'Queued'}
              </h1>
              <Pending run={r} />
            </>
          )}
        </>
      )}
    </div>
  )
}
