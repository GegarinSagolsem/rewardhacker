import { useCallback, useEffect, useState } from 'react'

export type ThemePref = 'light' | 'dark' | 'system'
const KEY = 'rh-theme'

function read(): ThemePref {
  try {
    // Light is the designed default; "system" and "dark" are opt-in from the theme toggle.
    const v = localStorage.getItem(KEY)
    return v === 'dark' || v === 'system' ? v : 'light'
  } catch {
    return 'light'
  }
}

function apply(pref: ThemePref) {
  const dark =
    pref === 'dark' || (pref === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches)
  document.documentElement.classList.toggle('dark', dark)
}

export function useTheme() {
  const [pref, setPref] = useState<ThemePref>(read)

  useEffect(() => {
    apply(pref)
    if (pref !== 'system') return
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = () => apply('system')
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [pref])

  const set = useCallback((next: ThemePref) => {
    try {
      localStorage.setItem(KEY, next)
    } catch {
      /* ignore */
    }
    setPref(next)
  }, [])

  return { pref, set }
}
