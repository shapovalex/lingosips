/**
 * CefrProfile — displays CEFR level badge and knowledge profile breakdown.
 *
 * TanStack Query keys:
 *   ["settings"]                               — active_target_language
 *   ["cefr", "profile", targetLanguage]        — CefrProfileResponse
 *
 * State machine: "loading" | "null-level" | "loaded" | "error"
 * Tone: neutral and factual — no gamification (UX-DR7).
 * AC: 1–6 (Story 5.2)
 */
import { useQuery } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { get } from "@/lib/client"
import { Skeleton } from "@/components/ui/skeleton"

// ─── Types ───────────────────────────────────────────────────────────────────

// Minimal local type — only what CefrProfile needs.
// Cross-feature imports from features/settings are forbidden.
interface SettingsResponse {
  active_target_language: string
}

type CefrProfileResponse = {
  level: string | null
  vocabulary_breadth: number
  grammar_coverage: number
  recall_rate_by_card_type: Record<string, number>
  active_passive_ratio: number | null
  explanation: string
}

type CefrProfileState = "loading" | "null-level" | "loaded" | "error"

// ─── CEFR threshold map — mirrors core/cefr.py exactly ───────────────────────

const CEFR_NEXT_VOCAB: Record<string, number | null> = {
  A1: 50,
  A2: 150,
  B1: 500,
  B2: 1200,
  C1: 2500,
  C2: null,
}

// ─── Component ───────────────────────────────────────────────────────────────

export function CefrProfile() {
  const { data: settings, isLoading: settingsLoading, isError: settingsError } = useQuery<SettingsResponse>({
    queryKey: ["settings"],
    queryFn: () => get<SettingsResponse>("/settings"),
  })

  const { data: profile, isLoading: profileLoading, isError: profileError } =
    useQuery<CefrProfileResponse>({
      queryKey: ["cefr", "profile", settings?.active_target_language],
      queryFn: () =>
        get<CefrProfileResponse>(
          `/cefr/profile?target_language=${settings!.active_target_language}`
        ),
      enabled: !!settings?.active_target_language,
    })

  // Derive state — enum-driven, no boolean flags
  const state: CefrProfileState =
    settingsError
      ? "error"
      : settingsLoading || profileLoading
        ? "loading"
        : !settings?.active_target_language
          ? "error"
          : profileError
            ? "error"
            : !profile || profile.level === null
              ? "null-level"
              : "loaded"

  // ── Loading ──────────────────────────────────────────────────────────────

  if (state === "loading") {
    return (
      <div role="region" aria-label="CEFR profile" aria-busy="true">
        <div className="flex flex-col gap-4">
          <Skeleton className="h-12 w-24 rounded-lg" />
          <Skeleton className="h-20 w-full rounded-lg" />
          <Skeleton className="h-20 w-full rounded-lg" />
          <Skeleton className="h-20 w-full rounded-lg" />
          <div className="grid grid-cols-2 gap-4">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-16 rounded-lg" />
            ))}
          </div>
        </div>
      </div>
    )
  }

  // ── Error ─────────────────────────────────────────────────────────────────

  if (state === "error") {
    return (
      <div role="alert">
        <p className="text-zinc-400">Unable to load CEFR profile.</p>
      </div>
    )
  }

  // ── Null level ────────────────────────────────────────────────────────────

  if (state === "null-level") {
    return (
      <div role="region" aria-label="CEFR profile">
        <p className="text-zinc-400">
          Keep practicing — your profile will appear after you review at least 10 cards.{" "}
          <Link to="/practice" search={{ mode: "self_assess" }} className="text-indigo-400 hover:underline">
            Go to practice
          </Link>
        </p>
      </div>
    )
  }

  // ── Loaded ────────────────────────────────────────────────────────────────

  const p = profile!

  // Pronunciation row
  const speakRecall = p.recall_rate_by_card_type?.["speak"]
  const speakDisplay =
    speakRecall !== undefined ? `${Math.round(speakRecall * 100)}%` : "No speak mode data yet"

  // Active vs. passive recall row
  const activePassiveDisplay =
    p.active_passive_ratio !== null
      ? `${Math.round(p.active_passive_ratio * 100)}%`
      : "No speak mode data yet"

  // ── "What you demonstrate confidently" ────────────────────────────────────

  const confidentItems: string[] = []
  confidentItems.push(p.explanation)
  confidentItems.push(`You know ${p.vocabulary_breadth} words in your target language.`)
  if (p.grammar_coverage > 0) {
    confidentItems.push(`You use ${p.grammar_coverage} grammar structures.`)
  }
  Object.entries(p.recall_rate_by_card_type ?? {}).forEach(([cardType, rate]) => {
    if (rate >= 0.8) {
      confidentItems.push(
        `Strong recall in ${cardType} practice (${Math.round(rate * 100)}%)`
      )
    }
  })

  // ── "Areas for development" ───────────────────────────────────────────────

  const developmentItems: string[] = []
  Object.entries(p.recall_rate_by_card_type ?? {}).forEach(([cardType, rate]) => {
    if (rate < 0.7) {
      developmentItems.push(
        `Improve ${cardType} recall (currently ${Math.round(rate * 100)}%)`
      )
    }
  })
  if (p.active_passive_ratio !== null && p.active_passive_ratio < 0.3) {
    developmentItems.push("Increase active recall practice — try write or speak modes")
  }
  if (developmentItems.length === 0) {
    developmentItems.push("Keep up your current pace — all areas are performing well")
  }

  // ── "Gap to the next level" ───────────────────────────────────────────────

  let gapMessage: string
  const nextVocab = CEFR_NEXT_VOCAB[p.level!]
  if (nextVocab == null) {
    gapMessage = "You've reached the highest CEFR level. Keep building vocabulary and grammar depth."
  } else {
    const vocabNeeded = nextVocab - p.vocabulary_breadth
    gapMessage =
      vocabNeeded > 0
        ? `Add ${vocabNeeded} more vocabulary words to reach the next CEFR level.`
        : "You have enough vocabulary — focus on grammar and recall consistency."
  }

  return (
    <div
      role="region"
      aria-label="CEFR profile"
      className="flex flex-col gap-8 max-w-2xl"
    >
      {/* Level badge */}
      <div className="rounded-lg bg-zinc-900 p-4 flex flex-col gap-1">
        <span className="text-2xl font-semibold text-zinc-50">{p.level}</span>
        <span className="text-xs text-zinc-400">Your estimated CEFR level</span>
      </div>

      {/* Three explanatory sub-sections */}
      <section aria-label="What you demonstrate confidently">
        <h3 className="text-sm font-medium text-zinc-300 mb-2">
          What you demonstrate confidently
        </h3>
        <ul className="space-y-1">
          {confidentItems.map((item, i) => (
            <li key={i} className="text-sm text-zinc-400">
              {item}
            </li>
          ))}
        </ul>
      </section>

      <section aria-label="Areas for development">
        <h3 className="text-sm font-medium text-zinc-300 mb-2">
          Areas for development
        </h3>
        <ul className="space-y-1">
          {developmentItems.map((item, i) => (
            <li key={i} className="text-sm text-zinc-400">
              {item}
            </li>
          ))}
        </ul>
      </section>

      <section aria-label="Gap to the next level">
        <h3 className="text-sm font-medium text-zinc-300 mb-2">
          Gap to the next level
        </h3>
        <p className="text-sm text-zinc-400">{gapMessage}</p>
      </section>

      {/* Four knowledge profile breakdown rows */}
      <section aria-label="Knowledge profile breakdown">
        <h3 className="text-sm font-medium text-zinc-300 mb-3">
          Knowledge profile breakdown
        </h3>
        <div role="list" className="grid grid-cols-2 gap-4">
          <BreakdownRow label="Vocabulary size" value={String(p.vocabulary_breadth)} />
          <BreakdownRow label="Grammar coverage" value={String(p.grammar_coverage)} />
          <BreakdownRow label="Pronunciation accuracy" value={speakDisplay} />
          <BreakdownRow label="Active vs. passive recall" value={activePassiveDisplay} />
        </div>
      </section>
    </div>
  )
}

// ─── Internal breakdown row ───────────────────────────────────────────────────

function BreakdownRow({ label, value }: { label: string; value: string }) {
  return (
    <div role="listitem" className="rounded-lg bg-zinc-900 p-4 flex flex-col gap-1">
      <span className="text-2xl font-semibold text-zinc-50">{value}</span>
      <span className="text-xs text-zinc-400">{label}</span>
    </div>
  )
}
