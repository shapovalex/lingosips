import { createFileRoute } from "@tanstack/react-router"

export const Route = createFileRoute("/progress")({
  component: ProgressPage,
})

function ProgressPage() {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-semibold text-zinc-50">Progress</h1>
      <p className="mt-2 text-zinc-400">Progress dashboard — implemented in Story 3.5.</p>
    </div>
  )
}
