import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { BookOpenText, ChevronDown, FileUp, Lock, Plus, Trash2 } from 'lucide-react'
import { useRef, useState, type FormEvent } from 'react'
import {
  Button,
  Card,
  CardHeader,
  EmptyState,
  ErrorBanner,
  Field,
  Input,
  Notice,
  PageHeader,
  Skeleton,
  Textarea,
} from '../components/ui'
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
    <Card className="animate-in mb-6">
      <CardHeader title="New guideline" />
      <form
        onSubmit={(e: FormEvent) => {
          e.preventDefault()
          add.mutate()
        }}
        className="grid gap-5 p-4 sm:p-5"
      >
        <Field label="Title">
          <Input required maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Task quality guidelines" />
        </Field>
        <Field
          label="Content (Markdown)"
          hint="Split into sections by heading and embedded for retrieval. Headings make better excerpts."
        >
          <Textarea
            required
            value={content}
            onChange={(e) => setContent(e.target.value)}
            rows={12}
            placeholder={'# Verifier tests\nTests must check exact values, not just the output format…'}
            className="font-mono text-[12.5px]"
          />
        </Field>
        {add.error && <ErrorBanner>{add.error.message}</ErrorBanner>}
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border pt-4">
          <Button type="button" variant="ghost" size="sm" onClick={() => file.current?.click()}>
            <FileUp /> Load a .md file
          </Button>
          <input
            ref={file}
            type="file"
            accept=".md,.markdown,.txt,text/markdown,text/plain"
            className="hidden"
            onChange={(e) => loadFile(e.target.files?.[0])}
          />
          <div className="flex gap-2">
            <Button variant="secondary" onClick={onDone}>
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
      <div className="flex items-center gap-3 px-4 py-3.5 sm:px-5">
        <button
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          className="group flex min-w-0 flex-1 items-center gap-3.5 text-left"
        >
          <span className="grid size-9 shrink-0 place-items-center rounded-xl border border-border bg-bg text-muted transition-colors group-hover:text-accent-ink">
            <BookOpenText className="size-4" />
          </span>
          <span className="min-w-0">
            <span className="block truncate text-[14px] font-medium">{g.title}</span>
            <span className="mt-0.5 block text-[12.5px] text-muted">
              <span className="font-mono text-[11.5px]">{g.chunk_count}</span> sections · added {timeAgo(g.created_at)}
            </span>
          </span>
          <ChevronDown className={clsx('ml-auto size-4 shrink-0 text-muted transition-transform', open && 'rotate-180')} />
        </button>
        {canEdit && (
          <Button
            variant="ghost"
            size="sm"
            className="size-9 px-0"
            aria-label={`Delete ${g.title}`}
            onClick={() => confirm(`Delete "${g.title}"?`) && del.mutate()}
            loading={del.isPending}
          >
            {!del.isPending && <Trash2 />}
          </Button>
        )}
      </div>
      {open && (
        <div className="animate-in border-t border-border bg-bg px-4 py-4 sm:px-5">
          {detail.data ? (
            <pre className="max-h-96 overflow-auto font-mono text-[12.5px] leading-relaxed whitespace-pre-wrap text-muted">
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
        eyebrow="Retrieval-augmented spec checks"
        title="Guidelines"
        description="Your team's written rules for good RL tasks. A guideline check finds the sections most relevant to a task and asks an LLM which ones the task breaks."
        actions={
          isAdmin &&
          org.llm_enabled &&
          !adding && (
            <Button onClick={() => setAdding(true)}>
              <Plus /> Add guideline
            </Button>
          )
        }
      />
      {!org.llm_enabled && (
        <Notice icon={<Lock />} className="mb-6">
          <span className="font-medium text-fg">AI features are off for this organization.</span> Guidelines and
          guideline checks use an LLM, which is opt-in per organization on the public demo to keep costs bounded. The
          static probes are free and always available.
        </Notice>
      )}
      {adding && <AddGuideline orgId={org.id} onDone={() => setAdding(false)} />}
      <Card>
        <CardHeader
          title="Library"
          aside={list.data?.length ? <span className="font-mono text-[12px]">{list.data.length}</span> : undefined}
        />
        {list.isPending ? (
          <div className="grid gap-3 p-5">
            <Skeleton className="h-10" />
          </div>
        ) : list.error ? (
          <div className="p-5">
            <ErrorBanner>{list.error.message}</ErrorBanner>
          </div>
        ) : list.data.length === 0 ? (
          <EmptyState icon={<BookOpenText />} title="No guidelines yet">
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
