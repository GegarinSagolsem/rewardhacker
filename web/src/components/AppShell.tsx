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
  Plus,
  Play,
  Users,
  X,
} from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { atLeast, useAuth } from '../lib/auth'
import type { Org } from '../lib/types'
import { Badge, Logo, ThemeToggle } from './ui'

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
        className="flex w-full items-center gap-2 rounded-lg border border-border bg-surface px-2 py-1.5 text-left shadow-card transition-colors hover:border-border-strong"
      >
        <span className="grid size-6 shrink-0 place-items-center rounded-md bg-accent-soft text-[11px] font-semibold text-accent uppercase">
          {org.name.slice(0, 1)}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[13px] font-medium">{org.name}</span>
          <span className="block text-[11px] text-muted capitalize">{org.role}</span>
        </span>
        <ChevronsUpDown className="size-3.5 text-muted" />
      </button>
      {open && (
        <div
          role="listbox"
          className="animate-in absolute inset-x-0 top-full z-30 mt-1 overflow-hidden rounded-lg border border-border bg-surface p-1 shadow-pop"
        >
          {me?.orgs.map((o) => (
            <button
              key={o.id}
              role="option"
              aria-selected={o.id === org.id}
              onClick={() => {
                setOpen(false)
                navigate(`/app/${o.id}/tasks`)
              }}
              className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-[13px] hover:bg-surface-2"
            >
              <span className="min-w-0 flex-1 truncate">{o.name}</span>
              {o.id === org.id && <Check className="size-3.5 text-accent" />}
            </button>
          ))}
          <div className="my-1 h-px bg-border" />
          <Link
            to="/app/new-org"
            onClick={() => setOpen(false)}
            className="flex items-center gap-2 rounded-md px-2 py-1.5 text-[13px] text-muted hover:bg-surface-2 hover:text-fg"
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
          'flex h-8 items-center gap-2 rounded-lg px-2 text-[13px] transition-colors',
          isActive ? 'bg-surface-2 font-medium text-fg' : 'text-muted hover:bg-surface-2/60 hover:text-fg',
        )
      }
    >
      <span className="[&>svg]:size-4">{icon}</span>
      {children}
    </NavLink>
  )
}

function Sidebar({ org }: { org: Org }) {
  const { me, logout } = useAuth()
  const base = `/app/${org.id}`
  return (
    <div className="flex h-full flex-col gap-4 p-3">
      <Link to="/" className="px-1 pt-1">
        <Logo className="text-[15px]" />
      </Link>
      <OrgSwitcher org={org} />
      <nav className="grid gap-0.5" aria-label="Main">
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
      <nav className="grid gap-0.5" aria-label="Organization">
        <div className="px-2 pb-1 text-[11px] font-medium text-subtle">Organization</div>
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
      <div className="mt-auto grid gap-3 border-t border-border pt-3">
        <div className="flex items-center justify-between gap-2 px-1">
          <span className="truncate text-xs text-muted" title={me?.email}>
            {me?.email}
          </span>
          <Badge className="capitalize">{org.role}</Badge>
        </div>
        <div className="flex items-center justify-between px-1">
          <ThemeToggle />
          <button
            onClick={logout}
            className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-muted hover:bg-surface-2 hover:text-fg"
          >
            <LogOut className="size-3.5" /> Sign out
          </button>
        </div>
      </div>
    </div>
  )
}

export function AppShell({ org, children }: { org: Org; children: ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false)
  const location = useLocation()
  useEffect(() => setMobileOpen(false), [location.pathname])

  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[232px_1fr]">
      <aside className="sticky top-0 hidden h-dvh border-r border-border bg-bg lg:block">
        <Sidebar org={org} />
      </aside>

      <header className="sticky top-0 z-20 flex h-12 items-center justify-between border-b border-border bg-bg/85 px-4 backdrop-blur lg:hidden">
        <Logo className="text-[15px]" />
        <button
          onClick={() => setMobileOpen(true)}
          aria-label="Open menu"
          className="grid size-8 place-items-center rounded-lg text-muted hover:bg-surface-2 hover:text-fg"
        >
          <Menu className="size-4" />
        </button>
      </header>
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/40" onClick={() => setMobileOpen(false)} />
          <div className="animate-in absolute inset-y-0 left-0 w-72 max-w-[85vw] border-r border-border bg-bg">
            <button
              onClick={() => setMobileOpen(false)}
              aria-label="Close menu"
              className="absolute top-3 right-3 grid size-8 place-items-center rounded-lg text-muted hover:bg-surface-2"
            >
              <X className="size-4" />
            </button>
            <Sidebar org={org} />
          </div>
        </div>
      )}

      <main className="min-w-0">
        <div className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 lg:px-10 lg:py-10">{children}</div>
      </main>
    </div>
  )
}
