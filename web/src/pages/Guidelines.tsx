import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BookOpenText, ChevronDown, FileUp, Plus, Trash2 } from 'lucide-react'
import { useRef, useState, type FormEvent } from 'react'
import { Button, Card, EmptyState, ErrorBanner, Field, Input, PageHeader, Skeleton } from '../components/ui'
import { api } from '../lib/api'
import { atLeast } from '../lib/auth'
import { timeAgo } from '../lib/format'
import { useOrg } from '../lib/org'
import type { Guideline } from '../lib/types'

function AddGuideline({ orgId, onDone }: { orgId: string; onDone: () => void }) {
  const qc = useQueryClient()
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const file = useRef<HTMLInputElement>(null)
  const add = useMutation({
    mutationFn: () => api.addGuideline(orgId, title, content),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['guidelines', orgId] })
      onDone()
    },
  })

  const loadFile = async (f: File | undefined) => {
    if (!f) return
    setContent(await f.text())
    if (!title) setTitle(f.name.replace(/\.(md|markdown|txt)$/i, ''))
  }

  return (
    <Card className="animate-in mb-6 p-4 sm:p-5">
      <form
        onSubmit={(e: FormEvent) => {
          e.preventDefault()
          add.mutate()
        }}
        className="grid gap-4"
      >
        <Field label="Title">
          <Input required maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Task quality guidelines" />
        </Field>
        <Field
          label="Content (Markdown)"
          hint="Split into sections by heading and embedded for retrieval. Headings make better excerpts."
        >
          <textarea
            required
            value={content}
            onChange={(e) => setContent(e.target.value)}
            rows={12}
            placeholder={'# Verifier tests\nTests must check exact values, not just the output format…'}
            className="w-full rounded-lg border border-border bg-surface px-3 py-2 font-mono text-[12px] leading-relaxed shadow-card placeholder:text-subtle hover:border-border-strong focus:border-accent focus:ring-3 focus:ring-accent/15 focus:outline-none"
          />
        </Field>
        {add.error && <ErrorBanner>{add.error.message}</ErrorBanner>}
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Button type="button" variant="ghost" size="sm" onClick={() => file.current?.click()}>
            <FileUp className="size-3.5" /> Load a .md file
          </Button>
          <input
            ref={file}
            type="file"
            accept=".md,.markdown,.txt,text/markdown,text/plain"
            className="hidden"
            onChange={(e) => loadFile(e.target.files?.[0])}
          />
          <div className="flex gap-2">
            <Button type="button" variant="secondary" onClick={onDone}>
              Cancel
            </Button>
            <Button type="submit" loading={add.isPending} disabled={!title.trim() || !content.trim()}>
              Add guideline
            </Button>
          </div>
        </div>
      </form>
    </Card>
  )
}

function GuidelineRow({ orgId, g, canEdit }: { orgId: string; g: Guideline; canEdit: boolean }) {
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const detail = useQuery({ queryKey: ['guideline', orgId, g.id], queryFn: () => api.guideline(orgId, g.id), enabled: open })
  const del = useMutation({
    mutationFn: () => api.deleteGuideline(orgId, g.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['guidelines', orgId] }),
  })
  return (
    <li className="border-b border-border last:border-0">
      <div className="flex items-center gap-3 px-4 py-3">
        <button
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          className="flex min-w-0 flex-1 items-center gap-3 text-left"
        >
          <span className="grid size-8 shrink-0 place-items-center rounded-lg border border-border bg-surface-2 text-muted">
            <BookOpenText className="size-4" />
          </span>
          <span className="min-w-0">
            <span className="block truncate text-[13px] font-medium">{g.title}</span>
            <span className="block text-xs text-muted">
              {g.chunk_count} sections · added {timeAgo(g.created_at)}
            </span>
          </span>
          <ChevronDown className={`ml-auto size-4 text-muted transition-transform ${open ? 'rotate-180' : ''}`} />
        </button>
        {canEdit && (
          <Button
            variant="ghost"
            size="sm"
            aria-label={`Delete ${g.title}`}
            onClick={() => confirm(`Delete "${g.title}"?`) && del.mutate()}
            loading={del.isPending}
          >
            <Trash2 className="size-3.5" />
          </Button>
        )}
      </div>
      {open && (
        <div className="animate-in border-t border-border bg-surface-2/40 px-4 py-3">
          {detail.data ? (
            <pre className="max-h-96 overflow-auto font-mono text-[12px] leading-relaxed whitespace-pre-wrap text-muted">
              {detail.data.content}
            </pre>
          ) : (
            <Skeleton className="h-20" />
          )}
        </div>
      )}
    </li>
  )
}

export default function Guidelines() {
  const org = useOrg()
  const isAdmin = atLeast(org.role, 'admin')
  const [adding, setAdding] = useState(false)
  const list = useQuery({ queryKey: ['guidelines', org.id], queryFn: () => api.guidelines(org.id) })

  return (
    <div className="animate-in">
      <PageHeader
        title="Guidelines"
        description="Your team's written rules for good RL tasks. A guideline check finds the sections most relevant to a task and asks an LLM which ones the task breaks."
        actions={
          isAdmin &&
          org.llm_enabled &&
          !adding && (
            <Button onClick={() => setAdding(true)}>
              <Plus className="size-3.5" /> Add guideline
            </Button>
          )
        }
      />
      {!org.llm_enabled && (
        <Card className="mb-4 p-4 text-[13px] text-muted">
          Guidelines and guideline checks use an LLM, which is opt-in per organization on the public demo to keep
          costs bounded. The static probes are free and always available.
        </Card>
      )}
      {adding && <AddGuideline orgId={org.id} onDone={() => setAdding(false)} />}
      <Card>
        {list.isPending ? (
          <div className="grid gap-3 p-4">
            <Skeleton className="h-10" />
          </div>
        ) : list.error ? (
          <div className="p-4">
            <ErrorBanner>{list.error.message}</ErrorBanner>
          </div>
        ) : list.data.length === 0 ? (
          <EmptyState icon={<BookOpenText className="size-4" />} title="No guidelines yet">
            {isAdmin
              ? 'Add your task-writing rules as Markdown. There is an example in examples/guidelines in the repo.'
              : 'An admin can add your team’s task-writing rules here.'}
          </EmptyState>
        ) : (
          <ul>
            {list.data.map((g) => (
              <GuidelineRow key={g.id} orgId={org.id} g={g} canEdit={isAdmin} />
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
