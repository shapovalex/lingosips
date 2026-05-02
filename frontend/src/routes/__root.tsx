import { createRootRouteWithContext, Outlet } from "@tanstack/react-router"
import type { QueryClient } from "@tanstack/react-query"
import { useQuery } from "@tanstack/react-query"
import { useEffect } from "react"
import { TooltipProvider } from "@/components/ui/tooltip"
import { SkipLink, IconSidebar, RightColumn, BottomNav } from "@/components/layout"
import { OnboardingWizard } from "@/features/onboarding"
import { QueueWidget } from "@/features/practice"
import { get } from "@/lib/client"
import type { components } from "@/lib/api"
import { usePracticeStore } from "@/lib/stores/usePracticeStore"
import { useAppStore } from "@/lib/stores/useAppStore"
import type { Notification } from "@/lib/stores/useAppStore"

// Generated type from api.d.ts (T8: replaced local interface after openapi-typescript run)
type SettingsResponse = components["schemas"]["SettingsResponse"]

interface RouterContext {
  queryClient: QueryClient
}

export const Route = createRootRouteWithContext<RouterContext>()({
  component: RootLayout,
})

// ── Notification toast system ─────────────────────────────────────────────────

/** Single toast notification. Auto-dismisses after 4 seconds. */
function NotificationItem({
  notification,
  onDismiss,
}: {
  notification: Notification
  onDismiss: () => void
}) {
  useEffect(() => {
    const timer = setTimeout(onDismiss, 4000)
    return () => clearTimeout(timer)
  }, [onDismiss])

  const bg =
    notification.type === "error"
      ? "bg-red-700"
      : notification.type === "warning"
        ? "bg-amber-700"
        : "bg-zinc-700"

  return (
    <div
      role="alert"
      className={`${bg} rounded-lg px-4 py-3 text-sm text-white shadow-lg flex items-start gap-2`}
    >
      <span className="flex-1">{notification.message}</span>
      <button
        onClick={onDismiss}
        aria-label="Dismiss notification"
        className="shrink-0 text-white/70 hover:text-white leading-none"
      >
        ×
      </button>
    </div>
  )
}

/** Fixed-position toast container — renders pending notifications from useAppStore. */
function NotificationList() {
  const notifications = useAppStore((s) => s.pendingNotifications)
  const dismiss = useAppStore((s) => s.dismissNotification)

  if (notifications.length === 0) return null

  return (
    <div
      aria-live="polite"
      className="fixed bottom-20 right-4 z-50 flex flex-col gap-2 max-w-xs w-full"
    >
      {notifications.map((n) => (
        <NotificationItem key={n.id} notification={n} onDismiss={() => dismiss(n.id)} />
      ))}
    </div>
  )
}

function RootLayout() {
  // T6.4: Fetch settings — drives onboarding gate
  const { data: settings, isLoading, isError, refetch } = useQuery({
    queryKey: ["settings"],
    queryFn: () => get<SettingsResponse>("/settings"),
  })

  // T4.1-T4.2: D4 layout — must be called unconditionally (Rules of Hooks)
  const sessionState = usePracticeStore((s) => s.sessionState)
  const isPracticing = sessionState === "active"

  // T6.5: Loading branch — show neutral skeleton while fetching
  if (isLoading) {
    return (
      <div
        className="flex h-screen bg-zinc-950"
        role="status"
        aria-label="Loading..."
      />
    )
  }

  // Error branch — settings fetch failed (network/server error). Show a retry
  // rather than falling through to the wizard, which would overwrite existing
  // settings for returning users if they clicked "Start learning".
  if (isError) {
    return (
      <div
        className="flex h-screen flex-col items-center justify-center bg-zinc-950 p-8"
        role="alert"
        aria-label="Connection error"
      >
        <div className="text-center space-y-4">
          <p className="text-zinc-400">Unable to connect to the lingosips server.</p>
          <button
            onClick={() => void refetch()}
            className="rounded-md bg-indigo-500 px-4 py-2 text-sm font-medium text-white
                       hover:bg-indigo-400 focus:outline-none focus:ring-2
                       focus:ring-indigo-500 focus:ring-offset-2 focus:ring-offset-zinc-950"
          >
            Try again
          </button>
        </div>
      </div>
    )
  }

  // T6.6: Onboarding branch — wizard replaces full layout until onboarding_completed
  if (!settings?.onboarding_completed) {
    return (
      <TooltipProvider>
        <OnboardingWizard />
      </TooltipProvider>
    )
  }

  // T6.7: Normal branch — existing app shell (unchanged)
  return (
    <TooltipProvider>
      {/* SkipLink must be FIRST focusable element in DOM — keyboard accessibility */}
      <SkipLink />

      {/* D2 layout: 64px sidebar | fluid main | 360px right column */}
      {/* flex-col on mobile (accordion stacks below main), flex-row on md+ */}
      {/* pb-16 md:pb-0 reserves space for the fixed BottomNav on mobile (≈64px) */}
      <div className="flex flex-col md:flex-row h-screen overflow-hidden bg-zinc-950 text-zinc-50 pb-16 md:pb-0">
        {/* D4: sidebar wrapper collapses when session is active */}
        <div
          data-testid="sidebar-wrapper"
          className={`
            transition-all duration-300 motion-reduce:duration-0
            ${isPracticing ? "w-0 overflow-hidden opacity-0 pointer-events-none" : ""}
          `}
        >
          <IconSidebar />
        </div>

        {/* Main content area — flex-1 fills remaining space; min-h-0 prevents */}
        {/* flex-col children from overflowing the h-screen container          */}
        {/* tabIndex={-1} allows programmatic focus from SkipLink              */}
        <main
          id="main-content"
          className="transition-all duration-300 motion-reduce:duration-0 flex-1 min-h-0 overflow-y-auto focus:outline-none"
          tabIndex={-1}
        >
          <Outlet />
        </main>

        {/* D4: right column wrapper collapses when session is active */}
        <div
          data-testid="right-column-wrapper"
          className={`
            transition-all duration-300 motion-reduce:duration-0
            ${isPracticing ? "w-0 overflow-hidden opacity-0 pointer-events-none" : ""}
          `}
        >
          <RightColumn><QueueWidget /></RightColumn>
        </div>
      </div>

      {/* BottomNav is fixed-positioned — must be OUTSIDE the h-screen flex container */}
      <BottomNav />

      {/* Toast notifications — rendered on top of all content */}
      <NotificationList />
    </TooltipProvider>
  )
}
