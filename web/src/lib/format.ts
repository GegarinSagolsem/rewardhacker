const rtf = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })

/** API timestamps are UTC; some (SQLite) arrive without an offset. */
export const parseUtc = (iso: string) =>
  new Date(iso.endsWith('Z') || /[+-]\d\d:\d\d$/.test(iso) ? iso : iso + 'Z').getTime()

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return '—'
  const then = parseUtc(iso)
  const sec = Math.round((then - Date.now()) / 1000)
  const abs = Math.abs(sec)
  if (abs < 45) return 'just now'
  if (abs < 3600) return rtf.format(Math.round(sec / 60), 'minute')
  if (abs < 86400) return rtf.format(Math.round(sec / 3600), 'hour')
  if (abs < 86400 * 30) return rtf.format(Math.round(sec / 86400), 'day')
  return new Date(then).toLocaleDateString('en', { day: 'numeric', month: 'short', year: 'numeric' })
}

export function duration(startIso: string | null, endIso: string | null): string {
  if (!startIso || !endIso) return '—'
  const s = Math.max(0, (parseUtc(endIso) - parseUtc(startIso)) / 1000)
  if (s < 60) return `${s.toFixed(s < 10 ? 1 : 0)}s`
  return `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`
}

export function usd(v: number | null | undefined): string {
  if (v == null) return '—'
  if (v === 0) return '$0'
  return v < 0.01 ? `$${v.toFixed(4)}` : `$${v.toFixed(2)}`
}

export const shortId = (id: string) => id.slice(0, 8)

/** task.yaml objectives are hard-wrapped; reflow single newlines, keep paragraph breaks. */
export const reflow = (text: string) => text.trim().replace(/([^\n])\n(?!\n)/g, '$1 ')
