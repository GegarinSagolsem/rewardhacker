import { useMutation, useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { ArrowLeft, CheckCircle2, Clock, Download, Loader2, ShieldCheck, Sparkles, Wrench } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Menu } from '../components/Menu'
import { TraceView } from '../components/TraceView'
import {
  Badge,
  Button,
  Card,
  ErrorBanner,
  Mono,
  SeverityBadge,
  Skeleton,
  StatusBadge,
  verdictTone,
} from '../components/ui'
import { api, downloadExport } from '../lib/api'
import { atLeast } from '../lib/auth'
import { shortId, timeAgo, usd } from '../lib/format'
import { useOrg } from '../lib/org'
import type { ExportKind, Finding, ProbeResult, Report, RunDetail as RunDetailT, TraceDoc, Verdict } from '../lib/types'

const VERDICT_COPY: Record<Verdict, { title: string; line: string }> = {
  exploitable: { title: 'Exploitable', line: 'The reward can be earned without doing the task.' },
  broken: { title: 'Broken', line: "The task can't be solved as specified: the verifier rejects the reference solution." },
  flaky: { title: 'Flaky', line: 'The verifier gives different answers for the same work.' },
  robust: { title: 'Robust', line: 'None of the probes that ran found a way to earn the reward without doing the work.' },
  inconclusive: { title: 'Inconclusive', line: 'No probe could run to completion, so there is nothing to conclude.' },
}

const dotColor: Record<string, string> = {
  red: 'bg-red',
  orange: 'bg-orange',
  amber: 'bg-amber',
  green: 'bg-green',
  neutral: 'bg-subtle',
}
const textColor: Record<string, string> = {
  red: 'text-red',
  orange: 'text-orange',
  amber: 'text-amber',
  green: 'text-green',
  neutral: 'text-muted',
}

function Stat({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="min-w-0 px-4 py-3">
      <div className="text-[11px] font-medium text-muted">{label}</div>
      <div className="mt-1 truncate text-[15px] font-medium tabular-nums">{children}</div>
    </div>
  )
}

function Section({ title, aside, children }: { title: string; aside?: ReactNode; children: ReactNode }) {
  return (
    <section className="mt-8">
      <div className="mb-3 flex items-baseline justify-between gap-4">
        <h2 className="text-sm font-semibold">{title}</h2>
        {aside && <div className="text-xs text-muted">{aside}</div>}
      </div>
      {children}
    </section>
  )
}

function FindingCard({ f }: { f: Finding }) {
  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center gap-2 px-4 pt-3.5">
        <SeverityBadge severity={f.severity} />
        <span className="font-medium">{f.title}</span>
        <Mono className="ml-auto text-subtle">{f.code}</Mono>
      </div>
      <p className="px-4 pt-2 pb-3.5 text-[13px] leading-relaxed whitespace-pre-wrap text-muted">{f.detail}</p>
      {f.recommendation && (
        <div className="flex gap-2.5 border-t border-border bg-surface-2/60 px-4 py-3 text-[13px]">
          <Wrench className="mt-0.5 size-3.5 shrink-0 text-accent" />
          <div>
            <span className="font-medium">How to fix · </span>
            <span className="text-muted">{f.recommendation}</span>
          </div>
        </div>
      )}
    </Card>
  )
}

function probeOutcome(p: ProbeResult): [string, 'green' | 'red' | 'amber' | 'neutral'] {
  if (p.status === 'finding') return ['Loophole', 'red']
  if (p.status === 'error') return ['Error', 'amber']
  if (p.status === 'skipped') return ['Skipped', 'neutral']
  return [p.expect_pass ? 'Passed' : 'Held', 'green']
}

function ProbesTable({ probes }: { probes: ProbeResult[] }) {
  return (
    <Card>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-[13px]">
          <thead>
            <tr className="border-b border-border text-xs text-muted">
              <th className="px-4 py-2.5 font-medium">Probe</th>
              <th className="px-4 py-2.5 font-medium">Result</th>
              <th className="hidden px-4 py-2.5 font-medium sm:table-cell">Verifier passed</th>
              <th className="hidden px-4 py-2.5 font-medium md:table-cell">Note</th>
            </tr>
          </thead>
          <tbody>
            {probes.map((p) => {
              const ran = p.trials.filter((t) => t.passed !== null)
              const passed = ran.filter((t) => t.passed).length
              const [label, tone] = probeOutcome(p)
              return (
                <tr key={p.name} className="border-b border-border last:border-0">
                  <td className="px-4 py-2.5">
                    <div className="font-mono text-[12px]">{p.name}</div>
                    <div className="text-xs text-muted">{p.title}</div>
                  </td>
                  <td className="px-4 py-2.5">
                    <Badge tone={tone} dot>
                      {label}
                    </Badge>
                  </td>
                  <td className="hidden px-4 py-2.5 sm:table-cell">
                    <Mono className="text-muted">{ran.length ? `${passed}/${ran.length}` : '—'}</Mono>
                    <span className="ml-1.5 text-[11px] text-subtle">{p.expect_pass ? 'should pass' : 'should fail'}</span>
                  </td>
                  <td className="hidden max-w-[280px] truncate px-4 py-2.5 text-xs text-muted md:table-cell" title={p.note ?? ''}>
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
            <Card key={`${probe}-${trial.index}`} className="p-4 sm:p-5">
              <div className="mb-4 flex flex-wrap items-center gap-2">
                <Sparkles className="size-3.5 text-accent" />
                <span className="text-[13px] font-medium">LLM agent told to earn the reward without doing the task</span>
                <Badge tone={trial.passed ? 'red' : 'green'} className="ml-auto">
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
    <div className="grid justify-items-end gap-1">
      <Menu
        trigger={({ toggle, open }) => (
          <Button variant="secondary" onClick={toggle} aria-expanded={open} loading={dl.isPending}>
            <Download className="size-3.5" /> Download report
          </Button>
        )}
        items={[
          { label: 'Markdown', hint: 'Readable; paste into a ticket or PR', onSelect: () => dl.mutate('report.md') },
          { label: 'JSON', hint: 'Full report with adversary traces', onSelect: () => dl.mutate('report.json') },
        ]}
      />
      {dl.error && <span className="text-xs text-red">{dl.error.message}</span>}
    </div>
  )
}

function Pending({ run }: { run: RunDetailT }) {
  const running = run.status === 'running'
  return (
    <Card className="flex items-start gap-3 p-5">
      {running ? (
        <Loader2 className="mt-0.5 size-4 animate-spin text-blue" />
      ) : (
        <Clock className="mt-0.5 size-4 text-muted" />
      )}
      <div>
        <div className="font-medium">{running ? 'Probing in Docker…' : 'Waiting for a worker'}</div>
        <p className="mt-1 text-[13px] text-muted">
          {running
            ? `Started ${timeAgo(run.started_at)}. Static probes take about a minute; the adversary adds ~30s. This page updates on its own.`
            : 'The run is queued. Start a worker with '}
          {!running && <Mono className="rounded bg-surface-2 px-1 py-0.5">uv run rh worker</Mono>}
          {!running && ' and it will be picked up.'}
        </p>
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
  const tone = verdict ? verdictTone[verdict] : 'neutral'
  const counted = report?.probes.filter((p) => p.status === 'ok' || p.status === 'finding') ?? []

  return (
    <div className="animate-in">
      <Link to={`/app/${org.id}/runs`} className="mb-4 inline-flex items-center gap-1 text-[13px] text-muted hover:text-fg">
        <ArrowLeft className="size-3.5" /> Runs
      </Link>

      {!r ? (
        <div className="grid gap-3">
          <Skeleton className="h-4 w-40" />
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-24" />
        </div>
      ) : (
        <>
          <div className="mb-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
            <span>
              Run <Mono>{shortId(r.id)}</Mono>
            </span>
            <span>·</span>
            <Link to={`/app/${org.id}/tasks/${r.task_id}`} className="font-mono hover:text-fg hover:underline">
              {task.data?.spec_id ?? shortId(r.task_id)}
            </Link>
            <span>·</span>
            <span>{timeAgo(r.created_at)}</span>
            {r.status !== 'done' && <StatusBadge status={r.status} />}
          </div>

          {r.status === 'done' && verdict ? (
            <>
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <h1 className="flex items-center gap-3 text-2xl font-semibold tracking-tight">
                    <span className={clsx('size-2.5 rounded-full', dotColor[tone])} />
                    <span className={textColor[tone]}>{VERDICT_COPY[verdict].title}</span>
                  </h1>
                  <p className="mt-1 text-[14px] text-muted">{VERDICT_COPY[verdict].line}</p>
                </div>
                {atLeast(org.role, 'reviewer') && <DownloadReport orgId={org.id} runId={r.id} />}
              </div>

              <Card className="mt-6 grid grid-cols-2 divide-border sm:grid-cols-4 sm:divide-x">
                <Stat label="Robustness score">
                  <span className={textColor[tone]}>{report!.score}</span>
                  <span className="text-muted">/100</span>
                </Stat>
                <Stat label="Probes that ran">
                  {counted.length}
                  <span className="text-muted">/{report!.probes.length}</span>
                </Stat>
                <Stat label="Duration">{report!.duration_sec.toFixed(1)}s</Stat>
                <Stat label="LLM cost">{r.include_llm ? usd(r.llm_cost_usd ?? 0) : <span className="text-muted">not used</span>}</Stat>
              </Card>

              <Section title="Findings" aside={report!.findings.length ? `${report!.findings.length} total` : undefined}>
                {report!.findings.length ? (
                  <div className="grid gap-3">
                    {report!.findings.map((f, i) => (
                      <FindingCard key={`${f.code}-${i}`} f={f} />
                    ))}
                  </div>
                ) : (
                  <Card className="flex items-center gap-3 p-4">
                    <ShieldCheck className="size-4 text-green" />
                    <span className="text-[13px]">No loopholes found.</span>
                    {!r.include_llm && (
                      <span className="text-xs text-muted">
                        Static probes only. Add the LLM adversary to look for task-specific shortcuts.
                      </span>
                    )}
                  </Card>
                )}
              </Section>

              <AdversarySection report={report!} traces={traces.data} />

              <Section
                title="Probes"
                aside={
                  <>
                    <CheckCircle2 className="mr-1 inline size-3" />
                    rewardhacker {report!.rewardhacker_version}
                  </>
                }
              >
                <ProbesTable probes={report!.probes} />
              </Section>
            </>
          ) : r.status === 'failed' ? (
            <>
              <h1 className="text-2xl font-semibold tracking-tight">Run failed</h1>
              <p className="mt-1 mb-6 text-[14px] text-muted">
                The task could not be probed. This usually means the environment failed to build.
              </p>
              <Card className="overflow-hidden">
                <pre className="overflow-x-auto p-4 font-mono text-[12px] whitespace-pre-wrap text-red">{r.error}</pre>
              </Card>
            </>
          ) : (
            <>
              <h1 className="mb-6 text-2xl font-semibold tracking-tight">
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
