import { Navigate, Outlet, Route, Routes, useLocation, useParams } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { Spinner } from './components/ui'
import { useAuth } from './lib/auth'
import Activity from './pages/Activity'
import ApiKeys from './pages/ApiKeys'
import AuthPage from './pages/AuthPage'
import Guidelines from './pages/Guidelines'
import Landing from './pages/Landing'
import Members from './pages/Members'
import NewOrg from './pages/NewOrg'
import NotFound from './pages/NotFound'
import RunDetail from './pages/RunDetail'
import Runs from './pages/Runs'
import TaskDetail from './pages/TaskDetail'
import Tasks from './pages/Tasks'

const LAST_ORG = 'rh-last-org'

function FullPageSpinner() {
  return (
    <div className="grid min-h-dvh place-items-center">
      <Spinner />
    </div>
  )
}

function RequireAuth() {
  const { token, me, loading } = useAuth()
  const location = useLocation()
  if (!token) return <Navigate to={`/login?next=${encodeURIComponent(location.pathname)}`} replace />
  if (loading || !me) return <FullPageSpinner />
  return <Outlet />
}

function RedirectIfAuthed({ children }: { children: React.ReactNode }) {
  const { token } = useAuth()
  return token ? <Navigate to="/app" replace /> : children
}

function OrgHome() {
  const { me } = useAuth()
  const orgs = me?.orgs ?? []
  if (!orgs.length) return <Navigate to="/app/new-org" replace />
  let last: string | null = null
  try {
    last = localStorage.getItem(LAST_ORG)
  } catch {
    /* ignore */
  }
  const org = orgs.find((o) => o.id === last) ?? orgs[0]
  return <Navigate to={`/app/${org.id}/tasks`} replace />
}

function OrgScope() {
  const { orgId } = useParams()
  const { me } = useAuth()
  const org = me?.orgs.find((o) => o.id === orgId)
  if (!org) return <Navigate to="/app" replace />
  try {
    localStorage.setItem(LAST_ORG, org.id)
  } catch {
    /* ignore */
  }
  return (
    <AppShell org={org}>
      <Outlet context={org} />
    </AppShell>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route
        path="/login"
        element={
          <RedirectIfAuthed>
            <AuthPage mode="login" />
          </RedirectIfAuthed>
        }
      />
      <Route
        path="/register"
        element={
          <RedirectIfAuthed>
            <AuthPage mode="register" />
          </RedirectIfAuthed>
        }
      />
      <Route path="/app" element={<RequireAuth />}>
        <Route index element={<OrgHome />} />
        <Route path="new-org" element={<NewOrg />} />
        <Route path=":orgId" element={<OrgScope />}>
          <Route index element={<Navigate to="tasks" replace />} />
          <Route path="tasks" element={<Tasks />} />
          <Route path="tasks/:taskId" element={<TaskDetail />} />
          <Route path="runs" element={<Runs />} />
          <Route path="runs/:runId" element={<RunDetail />} />
          <Route path="members" element={<Members />} />
          <Route path="guidelines" element={<Guidelines />} />
          <Route path="api-keys" element={<ApiKeys />} />
          <Route path="activity" element={<Activity />} />
        </Route>
      </Route>
      <Route path="*" element={<NotFound />} />
    </Routes>
  )
}
