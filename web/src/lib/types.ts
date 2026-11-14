// Mirrors src/rewardhacker/api/schemas.py and src/rewardhacker/models.py.

export type Role = 'viewer' | 'reviewer' | 'admin'
export type RunStatus = 'queued' | 'running' | 'done' | 'failed'
export type Verdict = 'robust' | 'exploitable' | 'broken' | 'flaky' | 'inconclusive'
export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info'

export interface User {
  id: string
  email: string
  created_at: string
}

export interface Org {
  id: string
  name: string
  created_at: string
  role: Role
}

export interface Me extends User {
  orgs: Org[]
}

export interface Member {
  user_id: string
  email: string
  role: Role
  created_at: string
}

export interface Task {
  id: string
  org_id: string
  spec_id: string
  objective: string
  uploaded_by: string | null
  created_at: string
}

export interface Run {
  id: string
  org_id: string
  task_id: string
  requested_by: string | null
  include_llm: boolean
  status: RunStatus
  attempts: number
  verdict: Verdict | null
  score: number | null
  llm_cost_usd: number | null
  error: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export interface ExecResult {
  exit_code: number | null
  stdout: string
  stderr: string
  timed_out: boolean
  duration_sec: number
}

export interface AgentStep {
  step: number
  text: string
  tool: string | null
  args: Record<string, unknown>
  output: string
}

export interface LLMUsage {
  model: string
  calls: number
  input_tokens: number
  output_tokens: number
  cost_usd: number
}

export interface AgentRun {
  steps: AgentStep[]
  explanation: string | null
  stop_reason: string
  error: string | null
  usage: LLMUsage
  judgement: 'shortcut' | 'genuine' | 'unknown' | null
  judge_reason: string | null
}

export interface Trial {
  index: number
  setup: ExecResult | null
  verify: ExecResult | null
  passed: boolean | null
  note: string | null
  agent: AgentRun | null
}

export interface ProbeResult {
  name: string
  title: string
  expect_pass: boolean
  status: 'ok' | 'finding' | 'skipped' | 'error'
  trials: Trial[]
  note: string | null
}

export interface Finding {
  code: string
  severity: Severity
  probe: string
  title: string
  detail: string
  recommendation: string
}

export interface Report {
  task_id: string
  image: string
  rewardhacker_version: string
  started_at: string
  duration_sec: number
  probes: ProbeResult[]
  findings: Finding[]
  score: number
  verdict: Verdict
  llm_usage: LLMUsage | null
}

export interface RunDetail extends Run {
  report: Report | null
  traces_stored: boolean
}

export interface TraceDoc extends AgentRun {
  run_id: string
  org_id: string
  task_id: string
  probe: string
  trial: number
}
