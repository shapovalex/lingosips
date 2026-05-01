import { createRootRouteWithContext, Outlet } from "@tanstack/react-router"
import type { QueryClient } from "@tanstack/react-query"

interface RouterContext {
  queryClient: QueryClient
}

export const Route = createRootRouteWithContext<RouterContext>()({
  component: RootLayout,
})

function RootLayout() {
  return (
    <div className="flex min-h-screen bg-zinc-950 text-zinc-50">
      {/* Sidebar placeholder — implemented in Story 1.2 */}
      <aside className="hidden w-64 shrink-0 border-r border-zinc-800 lg:block">
        <div className="flex h-full flex-col p-4">
          <div className="text-lg font-semibold text-zinc-100">lingosips</div>
          <nav className="mt-6 flex-1">
            {/* Navigation populated in Story 1.2 */}
          </nav>
        </div>
      </aside>

      {/* Main content area */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
