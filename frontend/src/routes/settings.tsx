import { createFileRoute } from "@tanstack/react-router"
import { ServiceStatusIndicator } from "@/components/ServiceStatusIndicator"

export const Route = createFileRoute("/settings")({
  component: SettingsPage,
})

function SettingsPage() {
  return (
    <div className="p-8">
      {/* ServiceStatusIndicator in header — mobile only (md+ uses sidebar footer) */}
      <div className="md:hidden mb-6 pb-4 border-b border-zinc-800">
        <ServiceStatusIndicator />
      </div>
      <h1 className="text-2xl font-semibold text-zinc-50">Settings</h1>
      <p className="mt-2 text-zinc-400">Settings — implemented in Story 2.3.</p>
    </div>
  )
}
