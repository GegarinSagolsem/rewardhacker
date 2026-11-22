import clsx from 'clsx'
import { useEffect, useRef, useState, type ReactNode } from 'react'

export interface MenuItem {
  label: ReactNode
  hint?: ReactNode
  onSelect: () => void
}

/** A small popover menu: click the trigger, pick an item. Closes on outside click and Escape. */
export function Menu({
  trigger,
  items,
  align = 'right',
}: {
  trigger: (props: { open: boolean; toggle: () => void }) => ReactNode
  items: MenuItem[]
  align?: 'left' | 'right'
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

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
      {trigger({ open, toggle: () => setOpen((v) => !v) })}
      {open && (
        <div
          role="menu"
          className={clsx(
            'animate-in absolute top-full z-30 mt-1.5 min-w-64 overflow-hidden rounded-xl border border-border bg-surface p-1 shadow-pop',
            align === 'right' ? 'right-0' : 'left-0',
          )}
        >
          {items.map((item, i) => (
            <button
              key={i}
              role="menuitem"
              onClick={() => {
                setOpen(false)
                item.onSelect()
              }}
              className="flex w-full flex-col items-start gap-0.5 rounded-lg px-3 py-2 text-left hover:bg-surface-2"
            >
              <span className="text-[13.5px] font-medium">{item.label}</span>
              {item.hint && <span className="text-[12px] text-muted">{item.hint}</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
