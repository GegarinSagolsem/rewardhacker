import { Sparkles } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { duration, shortId, timeAgo, usd } from '../lib/format'
import type { Run, Task } from '../lib/types'
import { Mono, ScoreMeter, StatusBadge, VerdictBadge } from './ui'

export function RunsTable({ orgId, runs, tasks }: { orgId: string; runs: Run[]; tasks?: Task[] }) {
  const navigate = useNavigate()
  const taskName = new Map(tasks?.map((t) => [t.id, t.spec_id]))

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-[13px]">
        <thead>
          <tr className="border-b border-border text-xs text-muted">
            <th className="px-4 py-2.5 font-medium">Run</th>
            {tasks && <th className="px-4 py-2.5 font-medium">Task</th>}
            <th className="px-4 py-2.5 font-medium">Status</th>
            <th className="px-4 py-2.5 font-medium">Verdict</th>
            <th className="hidden px-4 py-2.5 font-medium sm:table-cell">Score</th>
            <th className="hidden px-4 py-2.5 font-medium md:table-cell">Probes</th>
            <th className="hidden px-4 py-2.5 font-medium md:table-cell">Took</th>
            <th className="px-4 py-2.5 text-right font-medium">Started</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((r) => (
            <tr
              key={r.id}
              onClick={() => navigate(`/app/${orgId}/runs/${r.id}`)}
              className="group cursor-pointer border-b border-border last:border-0 hover:bg-surface-2/60"
            >
              <td className="px-4 py-2.5">
                <Link
                  to={`/app/${orgId}/runs/${r.id}`}
                  onClick={(e) => e.stopPropagation()}
                  className="text-fg group-hover:text-accent"
                >
                  <Mono>{shortId(r.id)}</Mono>
                </Link>
              </td>
              {tasks && (
                <td className="max-w-[220px] truncate px-4 py-2.5">
                  <Mono className="text-muted">{taskName.get(r.task_id) ?? shortId(r.task_id)}</Mono>
                </td>
              )}
              <td className="px-4 py-2.5">
                <StatusBadge status={r.status} />
              </td>
              <td className="px-4 py-2.5">
                {r.status === 'failed' ? <span className="text-subtle">—</span> : <VerdictBadge verdict={r.verdict} />}
              </td>
              <td className="hidden px-4 py-2.5 sm:table-cell">
                <ScoreMeter score={r.score} verdict={r.verdict} />
              </td>
              <td className="hidden px-4 py-2.5 md:table-cell">
                {r.include_llm ? (
                  <span className="inline-flex items-center gap-1 text-xs text-accent" title="Static probes + LLM adversary">
                    <Sparkles className="size-3" /> + adversary
                    {r.llm_cost_usd != null && <span className="text-muted">· {usd(r.llm_cost_usd)}</span>}
                  </span>
                ) : (
                  <span className="text-xs text-muted">static</span>
                )}
              </td>
              <td className="hidden px-4 py-2.5 md:table-cell">
                <Mono className="text-muted">{duration(r.started_at, r.finished_at)}</Mono>
              </td>
              <td className="px-4 py-2.5 text-right text-xs whitespace-nowrap text-muted">{timeAgo(r.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
