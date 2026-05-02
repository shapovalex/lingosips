import { createRootRouteWithContext, Outlet } from "@tanstack/react-router"
import type { QueryClient } from "@tanstack/react-query"
import { useQuery } from "@tanstack/react-query"
import { TooltipProvider } from "@/components/ui/tooltip"
import { SkipLink, IconSidebar, RightColumn, BottomNav } from "@/components/layout"
import { OnboardingWizard } from "@/features/onboarding"
import { QueueWidget } from "@/features/practice"
import { get } from "@/lib/client"
import type { components } from "@/lib/api"

// Generated type from api.d.ts (T8: replaced local interface after openapi-typescript run)
type SettingsResponse = components["schemas"]["SettingsResponse"]

interface RouterContext {
  queryClient: QueryClient
}

export const Route = createRootRouteWithContext<RouterContext>()({
  component: RootLayout,
})

function RootLayout() {
  // T6.4: Fetch settings — drives onboarding gate
  const { data: settings, isLoading, isError, refetch } = useQuery({
    queryKey: ["settings"],
    queryFn: () => get<SettingsResponse>("/settings"),
  })

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
        {/* Icon sidebar — hidden below md (768px), BottomNav takes over */}
        <IconSidebar />

        {/* Main content area — flex-1 fills remaining space; min-h-0 prevents */}
        {/* flex-col children from overflowing the h-screen container          */}
        {/* tabIndex={-1} allows programmatic focus from SkipLink              */}
        <main
          id="main-content"
          className="flex-1 min-h-0 overflow-y-auto focus:outline-none"
          tabIndex={-1}
        >
          <Outlet />
        </main>

        {/* Right column — 360px fixed on desktop, accordion on mobile */}
        <RightColumn><QueueWidget /></RightColumn>
      </div>

      {/* BottomNav is fixed-positioned — must be OUTSIDE the h-screen flex container */}
      <BottomNav />
    </TooltipProvider>
  )
}
