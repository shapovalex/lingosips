import { createFileRoute } from "@tanstack/react-router"

export const Route = createFileRoute("/settings")({
  component: SettingsPage,
})

function SettingsPage() {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-semibold text-zinc-50">Settings</h1>
      <p className="mt-2 text-zinc-400">Settings — implemented in Story 1.3+.</p>
    </div>
  )
}
