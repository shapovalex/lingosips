import { createRootRouteWithContext, Outlet } from "@tanstack/react-router"
import type { QueryClient } from "@tanstack/react-query"
import { TooltipProvider } from "@/components/ui/tooltip"
import { SkipLink, IconSidebar, RightColumn, BottomNav } from "@/components/layout"

interface RouterContext {
  queryClient: QueryClient
}

export const Route = createRootRouteWithContext<RouterContext>()({
  component: RootLayout,
})

function RootLayout() {
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
        <RightColumn />
      </div>

      {/* BottomNav is fixed-positioned — must be OUTSIDE the h-screen flex container */}
      <BottomNav />
    </TooltipProvider>
  )
}
