import clsx from 'clsx'
import {
  BookOpenText,
  Check,
  ChevronsUpDown,
  FolderArchive,
  History,
  KeyRound,
  LogOut,
  Menu,
  Play,
  Plus,
  Sparkles,
  Users,
  X,
} from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { atLeast, useAuth } from '../lib/auth'
import { shortId } from '../lib/format'
import type { Org } from '../lib/types'
import { Logo, ThemeToggle } from './ui'

const SECTIONS: Record<string, string> = {
  tasks: 'Tasks',
  runs: 'Runs',
  guidelines: 'Guidelines',
  members: 'Members',
  'api-keys': 'API keys',
  activity: 'Activity',
}

function OrgSwitcher({ org }: { org: Org }) {
  const { me } = useAuth()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false)
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="listbox"
        aria-expanded={open}
        className="flex w-full items-center gap-2.5 rounded-xl border border-border bg-surface px-2.5 py-2 text-left shadow-card transition-colors hover:border-border-strong"
      >
        <span className="grid size-7 shrink-0 place-items-center rounded-lg bg-ink font-mono text-[12px] font-semibold text-on-ink uppercase">
          {org.name.slice(0, 1)}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[13.5px] leading-tight font-semibold">{org.name}</span>
          <span className="label mt-0.5 block text-subtle">{org.role}</span>
        </span>
        <ChevronsUpDown className="size-3.5 text-muted" />
      </button>
      {open && (
        <div
          role="listbox"
          className="animate-in absolute inset-x-0 top-full z-30 mt-1.5 overflow-hidden rounded-xl border border-border bg-surface p-1 shadow-pop"
        >
          <div className="label px-2 pt-1.5 pb-1 text-subtle">Organizations</div>
          {me?.orgs.map((o) => (
            <button
              key={o.id}
              role="option"
              aria-selected={o.id === org.id}
              onClick={() => {
                setOpen(false)
                navigate(`/app/${o.id}/tasks`)
              }}
              className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-[13.5px] hover:bg-surface-2"
            >
              <span className="min-w-0 flex-1 truncate">{o.name}</span>
              {o.id === org.id && <Check className="size-3.5 text-accent-ink" />}
            </button>
          ))}
          <div className="my-1 h-px bg-border" />
          <Link
            to="/app/new-org"
            onClick={() => setOpen(false)}
            className="flex items-center gap-2 rounded-lg px-2 py-2 text-[13.5px] text-muted hover:bg-surface-2 hover:text-fg"
          >
            <Plus className="size-3.5" /> New organization
          </Link>
        </div>
      )}
    </div>
  )
}

function NavItem({ to, icon, children }: { to: string; icon: ReactNode; children: ReactNode }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        clsx(
          'group relative flex h-9 items-center gap-2.5 rounded-xl px-2.5 text-[14px] transition-colors',
          isActive
            ? 'bg-surface font-medium text-fg shadow-card ring-1 ring-border'
            : 'text-muted hover:bg-surface-2/70 hover:text-fg',
        )
      }
    >
      {({ isActive }) => (
        <>
          <span
            aria-hidden
            className={clsx(
              'absolute top-2 bottom-2 -left-3 w-[3px] rounded-r-sm transition-colors',
              isActive ? 'bg-accent' : 'bg-transparent',
            )}
          />
          <span className={clsx('[&>svg]:size-4', isActive ? 'text-accent-ink' : 'text-subtle group-hover:text-muted')}>
            {icon}
          </span>
          {children}
        </>
      )}
    </NavLink>
  )
}

function AiStatus({ org }: { org: Org }) {
  return (
    <div className="rounded-xl border border-border bg-surface px-3 py-2.5">
      <div className="flex items-center gap-2">
        <Sparkles className={clsx('size-3.5', org.llm_enabled ? 'text-accent-ink' : 'text-subtle')} />
        <span className="text-[12.5px] font-medium">{org.llm_enabled ? 'AI features on' : 'AI features off'}</span>
        <span className={clsx('ml-auto size-1.5', org.llm_enabled ? 'bg-green-fill' : 'bg-gray-fill')} aria-hidden />
      </div>
      <p className="mt-1 text-[12px] leading-snug text-muted">
        {org.llm_enabled
          ? 'LLM adversary, guidelines and spec checks are available.'
          : 'Static probes only. AI features are opt-in per organization.'}
      </p>
    </div>
  )
}

function Sidebar({ org }: { org: Org }) {
  const { me, logout } = useAuth()
  const base = `/app/${org.id}`
  return (
    <div className="flex h-full flex-col gap-6 overflow-y-auto px-4 pt-5 pb-4">
      <Link to="/" className="px-1" aria-label="RewardHacker home">
        <Logo className="text-[15px]" />
      </Link>
      <OrgSwitcher org={org} />
      <nav className="grid gap-1" aria-label="Main">
        <div className="label px-2.5 pb-1.5 text-subtle">Workspace</div>
        <NavItem to={`${base}/tasks`} icon={<FolderArchive />}>
          Tasks
        </NavItem>
        <NavItem to={`${base}/runs`} icon={<Play />}>
          Runs
        </NavItem>
        <NavItem to={`${base}/guidelines`} icon={<BookOpenText />}>
          Guidelines
        </NavItem>
      </nav>
      <nav className="grid gap-1" aria-label="Organization">
        <div className="label px-2.5 pb-1.5 text-subtle">Organization</div>
        <NavItem to={`${base}/members`} icon={<Users />}>
          Members
        </NavItem>
        {atLeast(org.role, 'admin') && (
          <>
            <NavItem to={`${base}/api-keys`} icon={<KeyRound />}>
              API keys
            </NavItem>
            <NavItem to={`${base}/activity`} icon={<History />}>
              Activity
            </NavItem>
          </>
        )}
      </nav>
      <div className="mt-auto grid gap-3">
        <AiStatus org={org} />
        <div className="grid gap-2.5 border-t border-border pt-3">
          <div className="flex items-center gap-2 px-1">
            <span className="grid size-6 shrink-0 place-items-center rounded-full bg-surface-2 text-[11px] font-semibold text-muted uppercase">
              {me?.email.slice(0, 1)}
            </span>
            <span className="min-w-0 truncate text-[12.5px] text-muted" title={me?.email}>
              {me?.email}
            </span>
          </div>
          <div className="flex items-center justify-between px-1">
            <ThemeToggle />
            <button
              onClick={logout}
              className="inline-flex items-center gap-1.5 rounded-xl px-2 py-1.5 text-[12.5px] text-muted hover:bg-surface-2 hover:text-fg"
            >
              <LogOut className="size-3.5" /> Sign out
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

/** "Org / Section / id" from the current URL, in the mono label style. */
function Breadcrumb({ org }: { org: Org }) {
  const { pathname } = useLocation()
  const [, , , section, id] = pathname.split('/')
  const label = SECTIONS[section ?? '']
  return (
    <nav aria-label="Breadcrumb" className="label flex min-w-0 items-center gap-2 text-subtle">
      <span className="truncate">{org.name}</span>
      {label && (
        <>
          <span aria-hidden>/</span>
          {id ? (
            <Link to={`/app/${org.id}/${section}`} className="hover:text-fg">
              {label}
            </Link>
          ) : (
            <span className="text-fg">{label}</span>
          )}
        </>
      )}
      {label && id && (
        <>
          <span aria-hidden>/</span>
          <span className="text-fg">{shortId(id)}</span>
        </>
      )}
    </nav>
  )
}

export function AppShell({ org, children }: { org: Org; children: ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false)
  const location = useLocation()
  useEffect(() => setMobileOpen(false), [location.pathname])

  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[256px_minmax(0,1fr)]">
      <aside className="sticky top-0 hidden h-dvh border-r border-border bg-bg lg:block">
        <Sidebar org={org} />
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-ink/45" onClick={() => setMobileOpen(false)} />
          <div className="animate-in absolute inset-y-0 left-0 w-[280px] max-w-[86vw] border-r border-border bg-bg shadow-pop">
            <button
              onClick={() => setMobileOpen(false)}
              aria-label="Close menu"
              className="absolute top-4 right-3 z-10 grid size-8 place-items-center rounded-xl text-muted hover:bg-surface-2"
            >
              <X className="size-4" />
            </button>
            <Sidebar org={org} />
          </div>
        </div>
      )}

      <div className="min-w-0">
        <header className="sticky top-0 z-20 border-b border-border bg-bg/90 backdrop-blur-sm">
          <div className="flex h-14 items-center gap-3 px-4 sm:px-6 lg:px-10">
            <button
              onClick={() => setMobileOpen(true)}
              aria-label="Open menu"
              className="-ml-1.5 grid size-9 place-items-center rounded-xl text-muted hover:bg-surface-2 hover:text-fg lg:hidden"
            >
              <Menu className="size-4.5" />
            </button>
            <Link to="/" className="shrink-0 lg:hidden" aria-label="RewardHacker home">
              <Logo className="text-[14px] [&>span:last-child]:hidden sm:[&>span:last-child]:inline" />
            </Link>
            <span className="h-5 w-px bg-border lg:hidden" aria-hidden />
            <Breadcrumb org={org} />
            <span
              className={clsx(
                'ml-auto hidden items-center gap-1.5 rounded-full border px-2 py-1 sm:inline-flex',
                org.llm_enabled ? 'border-accent/25 bg-accent-soft text-accent-ink' : 'border-border bg-surface text-muted',
              )}
              title={org.llm_enabled ? 'AI features are enabled for this organization' : 'AI features are off for this organization'}
            >
              <Sparkles className="size-3" />
              <span className="label">{org.llm_enabled ? 'AI on' : 'Static only'}</span>
            </span>
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1180px] px-4 pt-8 pb-16 sm:px-6 lg:px-10 lg:pt-10">{children}</main>
      </div>
    </div>
  )
}
