import { ArrowLeft } from 'lucide-react'
import { Link } from 'react-router-dom'
import { buttonClass } from '../components/styles'
import { Logo } from '../components/ui'

export default function NotFound() {
  return (
    <div className="relative flex min-h-dvh flex-col">
      <div
        aria-hidden
        className="bg-graph pointer-events-none absolute inset-0 [mask-image:radial-gradient(60%_55%_at_50%_45%,black,transparent)]"
      />
      <header className="relative px-5 py-5 sm:px-8">
        <Link to="/" aria-label="RewardHacker home">
          <Logo className="text-[15px]" />
        </Link>
      </header>
      <main className="relative grid flex-1 place-items-center px-5 pb-20">
        <div className="animate-in text-center">
          <div className="text-[96px] leading-none font-semibold tracking-[-0.06em] sm:text-[140px]">
            4<span className="text-accent">0</span>4
          </div>
          <div className="label mt-6 text-red">Verifier: failed</div>
          <h1 className="mt-3 text-[26px] font-semibold tracking-[-0.03em]">This page passed no tests.</h1>
          <p className="mt-2 text-[15px] text-muted">It doesn't exist, or you don't have access to it.</p>
          <Link to="/" className={buttonClass('secondary', 'md', 'mt-8')}>
            <ArrowLeft /> Go home
          </Link>
        </div>
      </main>
    </div>
  )
}
