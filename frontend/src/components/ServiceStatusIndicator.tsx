/**
 * ServiceStatusIndicator — always-visible sidebar footer widget showing active AI service.
 *
 * Placement: sidebar footer (desktop) and settings header (mobile via md:hidden wrapper).
 * Expands on click/Enter to show provider details and "Configure →" link to /settings.
 *
 * State machine: "cloud-active" | "local-active" | "cloud-degraded" | "switching" | "error"
 * Uses TanStack Query for polling (30s interval); Zustand for global simplified status flag.
 */

import { useEffect, useRef, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { get } from "@/lib/client"
import { useAppStore } from "@/lib/stores/useAppStore"
import { cn } from "@/lib/utils"

// ── Types ──────────────────────────────────────────────────────────────────

type ServiceIndicatorState = "cloud-active" | "local-active" | "cloud-degraded" | "switching" | "error"

interface LLMServiceStatus {
  provider: "openrouter" | "qwen_local"
  model: string | null
  last_latency_ms: number | null
  last_success_at: string | null
}

interface SpeechServiceStatus {
  provider: "azure" | "pyttsx3"
  last_latency_ms: number | null
  last_success_at: string | null
}

interface ServiceStatusData {
  llm: LLMServiceStatus
  speech: SpeechServiceStatus
}

// ── State derivation ────────────────────────────────────────────────────────

// Exported for direct unit testing (100% branch coverage requirement)
export function deriveIndicatorState(
  isLoading: boolean,
  isError: boolean,
  isStale: boolean,
  isFetching: boolean,
  data: ServiceStatusData | undefined
): ServiceIndicatorState {
  if (isLoading && !data) return "switching"
  if (isError && !data) return "error"
  if (!data) return "switching"
  if (data.llm.provider === "openrouter") {
    if (isStale && !isFetching && isError) return "cloud-degraded"
    return "cloud-active"
  }
  if (data.llm.provider === "qwen_local") return "local-active"
  return "error"
}

// ── Display mappings ────────────────────────────────────────────────────────

type StateDisplay = { label: string; dotClass: string; textClass: string }

// Exported for direct unit testing (100% branch coverage requirement)
export function getStateDisplay(state: ServiceIndicatorState, data: ServiceStatusData | undefined): StateDisplay {
  switch (state) {
    case "cloud-active":
      return {
        label: `OpenRouter · ${data?.llm.model ?? "..."}`,
        dotClass: "bg-emerald-500",
        textClass: "text-zinc-300",
      }
    case "local-active":
      return {
        label: "Local Qwen",
        dotClass: "bg-amber-500",
        textClass: "text-zinc-300",
      }
    case "cloud-degraded":
      return {
        label: "OpenRouter · slow",
        dotClass: "bg-amber-500",
        textClass: "text-zinc-300",
      }
    case "switching":
      return {
        label: "Connecting...",
        dotClass: "bg-zinc-500",
        textClass: "text-zinc-400",
      }
    case "error":
      return {
        label: "AI unavailable",
        dotClass: "bg-red-400",
        textClass: "text-zinc-400",
      }
  }
}

// ── Component ───────────────────────────────────────────────────────────────

export function ServiceStatusIndicator() {
  const [expanded, setExpanded] = useState(false)
  const [statusAnnouncement, setStatusAnnouncement] = useState("")
  const containerRef = useRef<HTMLDivElement>(null)
  const prevStateRef = useRef<ServiceIndicatorState | null>(null)

  const setServiceStatus = useAppStore((s) => s.setServiceStatus)

  const { data, isLoading, isError, isStale, isFetching } = useQuery<ServiceStatusData>({
    queryKey: ["services", "status"],
    queryFn: () => get<ServiceStatusData>("/services/status"),
    refetchInterval: 30_000,
    retry: 2,
  })

  const indicatorState = deriveIndicatorState(isLoading, isError, isStale, isFetching, data)
  const { label: displayLabel, dotClass, textClass } = getStateDisplay(indicatorState, data)

  // ── Announce state changes via aria-live ──────────────────────────────────
  useEffect(() => {
    if (prevStateRef.current !== null && prevStateRef.current !== indicatorState) {
      const { label } = getStateDisplay(indicatorState, data)
      setStatusAnnouncement(`AI service: ${label}`)
      const t = setTimeout(() => setStatusAnnouncement(""), 3_000)
      prevStateRef.current = indicatorState // always update ref so rapid data refreshes don't re-announce
      return () => clearTimeout(t)
    }
    prevStateRef.current = indicatorState
  }, [indicatorState, data])

  // ── Update Zustand global service status flag ─────────────────────────────
  useEffect(() => {
    if (!data) return
    const llmStatus = data.llm.provider === "openrouter" ? "cloud" : "local"
    const speechStatus = data.speech.provider === "azure" ? "cloud" : "local"
    setServiceStatus("llm", llmStatus)
    setServiceStatus("speech", speechStatus)
  }, [data, setServiceStatus])

  // ── Outside-click collapse ────────────────────────────────────────────────
  useEffect(() => {
    function handleOutsideClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setExpanded(false)
      }
    }
    if (expanded) document.addEventListener("mousedown", handleOutsideClick)
    return () => document.removeEventListener("mousedown", handleOutsideClick)
  }, [expanded])

  // ── Keyboard handler ──────────────────────────────────────────────────────
  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault()
      setExpanded((prev) => !prev)
    } else if (e.key === "Escape") {
      setExpanded(false)
    }
  }

  return (
    <div ref={containerRef} className="relative w-full px-2">
      {/* Always-in-DOM aria-live region — sr-only hides visually but keeps region registered */}
      <div aria-live="polite" aria-atomic="true" className="sr-only">
        {statusAnnouncement}
      </div>

      {/* Status badge button */}
      <button
        role="status"
        aria-expanded={expanded}
        aria-label={`AI service: ${displayLabel}. ${expanded ? "Click to collapse" : "Click to expand details"}`}
        onClick={() => setExpanded((prev) => !prev)}
        onKeyDown={handleKeyDown}
        className={cn(
          "flex w-full items-center gap-1.5 rounded px-2 py-1.5 text-xs hover:bg-zinc-800 focus:outline-none focus:ring-1 focus:ring-indigo-500",
          textClass
        )}
      >
        <span className={cn("h-2 w-2 shrink-0 rounded-full", dotClass)} aria-hidden="true" />
        <span className="min-w-0 truncate">{displayLabel}</span>
      </button>

      {/* Expanded detail panel — absolute, appears above badge (bottom-full for sidebar footer) */}
      {expanded && (
        <div className="absolute bottom-full left-0 mb-2 w-52 rounded-md border border-zinc-700 bg-zinc-900 p-3 shadow-lg text-xs">
          <div className="space-y-1.5 text-zinc-400">
            <div className="flex justify-between">
              <span className="text-zinc-500">Provider</span>
              <span className="text-zinc-300">
                {data?.llm.provider === "openrouter"
                  ? `OpenRouter · ${data.llm.model ?? "..."}`
                  : "Local Qwen"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Latency</span>
              <span className="text-zinc-300">
                {data?.llm.last_latency_ms != null ? `${data.llm.last_latency_ms}ms` : "—"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Last success</span>
              <span className="text-zinc-300 truncate max-w-[120px]">
                {data?.llm.last_success_at ?? "—"}
              </span>
            </div>
          </div>
          <div className="mt-2 pt-2 border-t border-zinc-800">
            <Link
              to="/settings"
              className="text-indigo-400 hover:text-indigo-300 text-xs font-medium"
            >
              Configure →
            </Link>
          </div>
        </div>
      )}
    </div>
  )
}
