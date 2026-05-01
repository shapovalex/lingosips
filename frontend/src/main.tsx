import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { QueryClientProvider } from "@tanstack/react-query"
import { RouterProvider, createRouter } from "@tanstack/react-router"
import "@fontsource-variable/inter"
import "./index.css"

import { queryClient } from "@/lib/queryClient"
import { routeTree } from "./routeTree.gen"

// Create the TanStack Router instance
const router = createRouter({
  routeTree,
  context: { queryClient },
})

// Register the router for type safety
declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router
  }
}

const rootElement = document.getElementById("root")!

createRoot(rootElement).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>
)
