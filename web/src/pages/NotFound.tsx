import { Link } from 'react-router-dom'
import { Logo } from '../components/ui'

export default function NotFound() {
  return (
    <div className="grid min-h-dvh place-items-center px-4">
      <div className="text-center">
        <Logo className="justify-center text-[15px]" />
        <p className="mt-8 font-mono text-xs text-muted">404</p>
        <h1 className="mt-1 text-xl font-semibold tracking-tight">This page passed no tests.</h1>
        <p className="mt-1 text-[13px] text-muted">It doesn't exist, or you don't have access to it.</p>
        <Link to="/" className="mt-6 inline-block text-[13px] font-medium text-accent hover:underline">
          Go home
        </Link>
      </div>
    </div>
  )
}
