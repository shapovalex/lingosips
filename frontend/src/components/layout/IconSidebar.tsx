import { Home, BookOpen, Upload, BarChart3, Settings } from "lucide-react"
import { Link } from "@tanstack/react-router"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"

const NAV_ITEMS = [
  { to: "/", icon: Home, label: "Home", ariaLabel: "Home — card creation" },
  { to: "/practice", icon: BookOpen, label: "Practice", ariaLabel: "Practice" },
  { to: "/import", icon: Upload, label: "Import", ariaLabel: "Import" },
  { to: "/progress", icon: BarChart3, label: "Progress", ariaLabel: "Progress" },
  { to: "/settings", icon: Settings, label: "Settings", ariaLabel: "Settings" },
] as const

/**
 * IconSidebar — 64px fixed icon sidebar for desktop navigation (md+).
 * Hidden below 768px (BottomNav takes over).
 * Width is ALWAYS w-16 (64px) — never collapses or expands per spec.
 */
export function IconSidebar() {
  return (
    <div className="hidden md:flex w-16 shrink-0 flex-col border-r border-zinc-800 bg-zinc-950">
      <nav aria-label="Main navigation" className="flex flex-1 flex-col items-center gap-2 py-4">
        {NAV_ITEMS.map(({ to, icon: Icon, label, ariaLabel }) => (
          <Tooltip key={to}>
            <TooltipTrigger asChild>
              <Link
                to={to}
                aria-label={ariaLabel}
                className="flex items-center justify-center min-h-[44px] min-w-[44px] rounded-lg transition-colors"
                activeProps={{ className: "bg-indigo-500 text-white" }}
                inactiveProps={{ className: "text-zinc-400 hover:text-zinc-50 hover:bg-zinc-800" }}
              >
                <Icon size={20} aria-hidden="true" />
              </Link>
            </TooltipTrigger>
            <TooltipContent side="right">{label}</TooltipContent>
          </Tooltip>
        ))}
      </nav>

      {/* Footer area — ServiceStatusIndicator placeholder for Story 1.10 */}
      <div className="flex flex-col items-center py-4">
        {/* ServiceStatusIndicator — Story 1.10 */}
      </div>
    </div>
  )
}
