import { useState } from "react"
import { ChevronUp } from "lucide-react"

/** Enum-driven state machine — never boolean flags (project-context.md rule) */
type RightColumnState = "expanded" | "collapsed"

interface RightColumnProps {
  children?: React.ReactNode
}

/**
 * RightColumn — 360px fixed right column on desktop.
 * On mobile: stacks below main content as a collapsible accordion.
 * State machine: "expanded" | "collapsed" (default: collapsed on mobile).
 */
export function RightColumn({ children }: RightColumnProps) {
  const [state, setState] = useState<RightColumnState>("collapsed")

  function toggle() {
    setState((prev) => (prev === "collapsed" ? "expanded" : "collapsed"))
  }

  return (
    <>
      {/* Desktop: always visible, 360px fixed right column */}
      <aside aria-label="Right column" className="hidden md:block w-[360px] shrink-0 border-l border-zinc-800 bg-zinc-950 overflow-y-auto">
        {/* QueueWidget — populated in Story 1.9 */}
        {children}
      </aside>

      {/* Mobile: accordion below main content */}
      <div className="md:hidden border-t border-zinc-800">
        <button
          onClick={toggle}
          className="flex w-full items-center justify-between p-4 text-sm text-zinc-400 hover:text-zinc-50 transition-colors"
          aria-expanded={state === "expanded"}
          aria-controls="right-column-mobile-content"
        >
          <span>{state === "collapsed" ? "Cards due · Practice →" : "Close"}</span>
          <ChevronUp
            size={16}
            aria-hidden="true"
            className={state === "expanded" ? "" : "rotate-180"}
          />
        </button>
        {state === "expanded" && (
          <div
            id="right-column-mobile-content"
            className="p-4"
            data-testid="right-column-mobile-body"
          >
            {/* QueueWidget — populated in Story 1.9 */}
            {children}
          </div>
        )}
      </div>
    </>
  )
}
