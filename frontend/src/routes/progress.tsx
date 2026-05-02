import { createFileRoute } from "@tanstack/react-router"
import { ProgressDashboard } from "@/features/progress"

export const Route = createFileRoute("/progress")({
  component: ProgressPage,
})

function ProgressPage() {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-semibold text-zinc-50 mb-6">Progress</h1>
      <ProgressDashboard />
    </div>
  )
}
