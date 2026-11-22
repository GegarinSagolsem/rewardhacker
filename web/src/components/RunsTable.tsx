import { ArrowUpRight, Sparkles } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { duration, shortId, timeAgo, usd } from '../lib/format'
import type { Run, Task } from '../lib/types'
import { Mono, ScoreMeter, StatusBadge, VerdictBadge } from './ui'

/** Shared table styling: mono uppercase heads, generous rows, hairline separators. */
export const TH = 'label px-4 py-3 text-left font-medium whitespace-nowrap text-muted first:pl-5 last:pr-5'
export const TD = 'px-4 py-3.5 first:pl-5 last:pr-5'
export const THEAD_ROW = 'border-b border-border bg-surface-2/40'
export const TBODY_ROW = 'group cursor-pointer border-b border-border last:border-0 transition-colors hover:bg-bg'

export function RunsTable({
  orgId,
  runs,
  tasks,
  compact,
}: {
  orgId: string
  runs: Run[]
  tasks?: Task[]
  /** Narrow container: drop the probes column until very wide screens. */
  compact?: boolean
}) {
  const navigate = useNavigate()
  const probesCol = compact ? 'hidden 2xl:table-cell' : 'hidden md:table-cell'
  const taskName = new Map(tasks?.map((t) => [t.id, t.spec_id]))

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[13.5px]">
        <thead>
          <tr className={THEAD_ROW}>
            <th className={TH}>Run</th>
            {tasks && <th className={`${TH} hidden sm:table-cell`}>Task</th>}
            <th className={`${TH} hidden sm:table-cell`}>Status</th>
            <th className={TH}>Verdict</th>
            <th className={`${TH} hidden sm:table-cell`}>Score</th>
            <th className={`${TH} ${probesCol}`}>Probes</th>
            <th className={`${TH} hidden md:table-cell`}>Took</th>
            <th className={`${TH} text-right`}>Started</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((r) => (
            <tr key={r.id} onClick={() => navigate(`/app/${orgId}/runs/${r.id}`)} className={TBODY_ROW}>
              <td className={TD}>
                <Link
                  to={`/app/${orgId}/runs/${r.id}`}
                  onClick={(e) => e.stopPropagation()}
                  className="inline-flex items-center gap-1 font-medium text-fg group-hover:text-accent-ink"
                >
                  <Mono>{shortId(r.id)}</Mono>
                  <ArrowUpRight className="size-3 opacity-0 transition-opacity group-hover:opacity-100" />
                </Link>
                {tasks && (
                  <div className="mt-0.5 max-w-[46vw] truncate font-mono text-[11.5px] text-muted sm:hidden">
                    {taskName.get(r.task_id) ?? shortId(r.task_id)}
                  </div>
                )}
              </td>
              {tasks && (
                <td className={`${TD} hidden max-w-[240px] truncate sm:table-cell`}>
                  <Mono className="text-muted">{taskName.get(r.task_id) ?? shortId(r.task_id)}</Mono>
                </td>
              )}
              <td className={`${TD} hidden sm:table-cell`}>
                <StatusBadge status={r.status} />
              </td>
              <td className={TD}>
                {r.status === 'done' ? (
                  <VerdictBadge verdict={r.verdict} />
                ) : (
                  <>
                    <span className="text-subtle max-sm:hidden">—</span>
                    <span className="sm:hidden">
                      <StatusBadge status={r.status} />
                    </span>
                  </>
                )}
              </td>
              <td className={`${TD} hidden sm:table-cell`}>
                <ScoreMeter score={r.score} verdict={r.verdict} />
              </td>
              <td className={`${TD} ${probesCol}`}>
                {r.include_llm ? (
                  <span
                    className="inline-flex items-center gap-1.5 text-[12.5px] whitespace-nowrap text-accent-ink"
                    title="Static probes + LLM adversary"
                  >
                    <Sparkles className="size-3" /> + adversary
                    {r.llm_cost_usd != null && <span className="font-mono text-[11.5px] text-muted">{usd(r.llm_cost_usd)}</span>}
                  </span>
                ) : (
                  <span className="text-[12.5px] text-muted">static</span>
                )}
              </td>
              <td className={`${TD} hidden md:table-cell`}>
                <Mono className="whitespace-nowrap text-muted">{duration(r.started_at, r.finished_at)}</Mono>
              </td>
              <td className={`${TD} text-right text-[12.5px] whitespace-nowrap text-muted`}>{timeAgo(r.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
