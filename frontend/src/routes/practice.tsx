import { createFileRoute } from "@tanstack/react-router"

export const Route = createFileRoute("/practice")({
  component: PracticePage,
})

function PracticePage() {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-semibold text-zinc-50">Practice</h1>
      <p className="mt-2 text-zinc-400">Practice session — implemented in Story 1.7.</p>
    </div>
  )
}
