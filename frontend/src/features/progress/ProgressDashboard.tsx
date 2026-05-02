/**
 * ProgressDashboard — shows vocabulary size, learned cards, 30-day activity, recall rate.
 *
 * TanStack Query key: ["progress", "dashboard"]
 * Tone: neutral and factual — no gamification, no streaks, no stars.
 * AC: 1, 2 (Story 3.5)
 */
import { useQuery } from "@tanstack/react-query"
import { get } from "@/lib/client"
import { Skeleton } from "@/components/ui/skeleton"

type DashboardData = {
  total_cards: number
  learned_cards: number
  review_count_by_day: Array<{ date: string; count: number }>
  overall_recall_rate: number
}

type DashboardState = "loading" | "loaded" | "empty" | "error"

export function ProgressDashboard() {
  const { data, isLoading, isError } = useQuery<DashboardData>({
    queryKey: ["progress", "dashboard"],
    queryFn: () => get<DashboardData>("/progress/dashboard"),
  })

  const state: DashboardState = isLoading
    ? "loading"
    : isError
      ? "error"
      : !data || data.total_cards === 0
        ? "empty"
        : "loaded"

  if (state === "loading") {
    return (
      <div role="region" aria-label="Progress dashboard" aria-busy="true">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-20 rounded-lg" />
          ))}
        </div>
        <Skeleton className="mt-6 h-16 w-full rounded" />
      </div>
    )
  }

  if (state === "error") {
    return (
      <div role="alert">
        <p className="text-zinc-400">Unable to load progress data.</p>
      </div>
    )
  }

  if (state === "empty") {
    return (
      <div role="region" aria-label="Progress dashboard">
        <p className="text-zinc-400">
          No reviews yet — start practicing to see your progress.
        </p>
      </div>
    )
  }

  const recallPercent = Math.round(data!.overall_recall_rate * 100)
  const maxDailyCount = Math.max(
    ...data!.review_count_by_day.map((d) => d.count),
    1
  )
  const totalReviews = data!.review_count_by_day.reduce((s, d) => s + d.count, 0)

  return (
    <div
      role="region"
      aria-label="Progress dashboard"
      className="flex flex-col gap-8 max-w-2xl"
    >
      {/* Metric grid: 4 numbers */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <MetricCard label="Total cards" value={data!.total_cards} />
        <MetricCard label="Learned" value={data!.learned_cards} />
        <MetricCard label="Recall rate" value={`${recallPercent}%`} />
        <MetricCard label="Due today" value="..." />
      </div>

      {/* 30-day activity bar chart — pure CSS, no charting library */}
      <section aria-label="Review activity last 30 days">
        <h3 className="text-sm text-zinc-400 mb-3">Reviews last 30 days</h3>
        <div
          className="flex items-end gap-px h-16"
          role="img"
          aria-label={`Review activity over the last 30 days. Total: ${totalReviews} reviews.`}
        >
          {data!.review_count_by_day.map((day) => (
            <div
              key={day.date}
              className="flex-1 bg-indigo-500 rounded-sm min-h-px"
              style={{
                height: `${Math.round((day.count / maxDailyCount) * 100)}%`,
              }}
              title={`${day.date}: ${day.count} reviews`}
            />
          ))}
          {data!.review_count_by_day.length === 0 && (
            <p className="text-zinc-500 text-sm self-center w-full text-center">
              No reviews yet
            </p>
          )}
        </div>
      </section>
    </div>
  )
}

// Internal metric card — neutral, no gamification
function MetricCard({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-lg bg-zinc-900 p-4 flex flex-col gap-1">
      <span className="text-2xl font-semibold text-zinc-50">{value}</span>
      <span className="text-xs text-zinc-400">{label}</span>
    </div>
  )
}
