import { Home, BookOpen, LibraryBig, Upload, BarChart3, Settings } from "lucide-react"
import { Link } from "@tanstack/react-router"

const NAV_ITEMS = [
  { to: "/", icon: Home, label: "Home", ariaLabel: "Home — card creation" },
  { to: "/practice", icon: BookOpen, label: "Practice", ariaLabel: "Practice" },
  { to: "/decks", icon: LibraryBig, label: "Decks", ariaLabel: "Decks — vocabulary organization" },
  { to: "/import", icon: Upload, label: "Import", ariaLabel: "Import" },
  { to: "/progress", icon: BarChart3, label: "Progress", ariaLabel: "Progress" },
  { to: "/settings", icon: Settings, label: "Settings", ariaLabel: "Settings" },
] as const

/**
 * BottomNav — fixed bottom navigation bar for mobile (<768px).
 * Replaces IconSidebar on small viewports.
 * Rendered as a sibling OUTSIDE the h-screen flex container (fixed positioning).
 */
export function BottomNav() {
  return (
    <nav
      aria-label="Bottom navigation"
      className="fixed bottom-0 left-0 right-0 flex md:hidden bg-zinc-900 border-t border-zinc-800 z-40"
    >
      {NAV_ITEMS.map(({ to, icon: Icon, label, ariaLabel }) => (
        <Link
          key={to}
          to={to}
          aria-label={ariaLabel}
          className="flex flex-col items-center gap-1 py-2 px-3 text-xs flex-1 min-h-[44px]"
          activeProps={{ className: "text-indigo-500" }}
          inactiveProps={{ className: "text-zinc-400" }}
        >
          <Icon size={20} aria-hidden="true" />
          <span>{label}</span>
        </Link>
      ))}
    </nav>
  )
}
