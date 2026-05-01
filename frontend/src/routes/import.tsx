import { createFileRoute } from "@tanstack/react-router"

export const Route = createFileRoute("/import")({
  component: ImportPage,
})

function ImportPage() {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-semibold text-zinc-50">Import</h1>
      <p className="mt-2 text-zinc-400">Import pipeline — implemented in Story 2.4.</p>
    </div>
  )
}
