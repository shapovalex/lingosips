/**
 * Tests for SessionSummary component.
 * TDD: written before implementation.
 * AC: 8
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { SessionSummary } from "./SessionSummary"

// Mock the router navigate
const mockNavigate = vi.fn()
vi.mock("@tanstack/react-router", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@tanstack/react-router")>()
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

// Mock usePracticeStore
vi.mock("@/lib/stores/usePracticeStore", () => ({
  usePracticeStore: vi.fn((selector) => {
    const state = {
      sessionState: "complete" as const,
      mode: "self_assess" as const,
      currentCardIndex: 0,
      sessionCount: 1,
      startSession: vi.fn(),
      endSession: vi.fn(),
      nextCard: vi.fn(),
      prevCard: vi.fn(),
    }
    return selector(state)
  }),
}))

import { usePracticeStore } from "@/lib/stores/usePracticeStore"

// Future nextDue (1 day from now)
const FUTURE_NEXT_DUE = new Date(Date.now() + 25 * 60 * 60 * 1000).toISOString()  // 25h from now

describe("SessionSummary", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
    // Re-mock with fresh endSession spy
    vi.mocked(usePracticeStore).mockImplementation((selector) => {
      const state = {
        sessionState: "complete" as const,
        mode: "self_assess" as const,
        currentCardIndex: 0,
        sessionCount: 1,
        startSession: vi.fn(),
        endSession: vi.fn(),
        nextCard: vi.fn(),
        prevCard: vi.fn(),
      }
      return selector(state)
    })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  // ── Data display ───────────────────────────────────────────────────────────

  it("shows cards reviewed count", () => {
    render(<SessionSummary cardsReviewed={12} recallRate={0.75} nextDue={null} />)
    expect(screen.getByText(/12 cards reviewed/i)).toBeInTheDocument()
  })

  it("shows recall rate as percentage", () => {
    render(<SessionSummary cardsReviewed={10} recallRate={0.75} nextDue={null} />)
    expect(screen.getByText(/75% recall rate/i)).toBeInTheDocument()
  })

  it("shows 'All caught up!' when nextDue is null", () => {
    render(<SessionSummary cardsReviewed={5} recallRate={1.0} nextDue={null} />)
    expect(screen.getByText(/all caught up/i)).toBeInTheDocument()
  })

  it("shows 'Cards due now' when nextDue is within 1 hour", () => {
    const soonDue = new Date(Date.now() + 30 * 60 * 1000).toISOString()  // 30 mins
    render(<SessionSummary cardsReviewed={5} recallRate={0.8} nextDue={soonDue} />)
    expect(screen.getByText(/cards due now/i)).toBeInTheDocument()
  })

  it("formats next due date with relative time when more than 1 hour away", () => {
    render(<SessionSummary cardsReviewed={5} recallRate={0.8} nextDue={FUTURE_NEXT_DUE} />)
    // Should contain "in X" (relative time format)
    expect(screen.getByText(/in \d+ day/i)).toBeInTheDocument()
  })

  it("shows neutral tone — no stars, congratulations, or streaks", () => {
    render(<SessionSummary cardsReviewed={5} recallRate={1.0} nextDue={null} />)
    expect(screen.queryByText(/great job/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/streak/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/congratulations/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/⭐/)).not.toBeInTheDocument()
  })

  // ── Return to home ─────────────────────────────────────────────────────────

  it("'Return to home' button calls endSession and navigates", () => {
    const endSessionMock = vi.fn()
    vi.mocked(usePracticeStore).mockImplementation((selector) => {
      const state = {
        sessionState: "complete" as const,
        mode: "self_assess" as const,
        currentCardIndex: 0,
        sessionCount: 1,
        startSession: vi.fn(),
        endSession: endSessionMock,
        nextCard: vi.fn(),
        prevCard: vi.fn(),
      }
      return selector(state)
    })

    render(<SessionSummary cardsReviewed={5} recallRate={0.8} nextDue={null} />)
    fireEvent.click(screen.getByRole("button", { name: /return to home/i }))
    expect(endSessionMock).toHaveBeenCalled()
    expect(mockNavigate).toHaveBeenCalledWith({ to: "/" })
  })

  // ── Auto-return ────────────────────────────────────────────────────────────

  it("auto-returns home after 5 seconds", async () => {
    const endSessionMock = vi.fn()
    vi.mocked(usePracticeStore).mockImplementation((selector) => {
      const state = {
        sessionState: "complete" as const,
        mode: "self_assess" as const,
        currentCardIndex: 0,
        sessionCount: 1,
        startSession: vi.fn(),
        endSession: endSessionMock,
        nextCard: vi.fn(),
        prevCard: vi.fn(),
      }
      return selector(state)
    })

    render(<SessionSummary cardsReviewed={5} recallRate={0.8} nextDue={null} />)
    vi.advanceTimersByTime(5000)
    expect(endSessionMock).toHaveBeenCalled()
    expect(mockNavigate).toHaveBeenCalledWith({ to: "/" })
  })

  it("cancels auto-return timer on unmount", () => {
    const endSessionMock = vi.fn()
    vi.mocked(usePracticeStore).mockImplementation((selector) => {
      const state = {
        sessionState: "complete" as const,
        mode: "self_assess" as const,
        currentCardIndex: 0,
        sessionCount: 1,
        startSession: vi.fn(),
        endSession: endSessionMock,
        nextCard: vi.fn(),
        prevCard: vi.fn(),
      }
      return selector(state)
    })

    const { unmount } = render(<SessionSummary cardsReviewed={5} recallRate={0.8} nextDue={null} />)
    unmount()
    vi.advanceTimersByTime(5000)
    // After unmount, endSession and navigate should NOT be called
    expect(endSessionMock).not.toHaveBeenCalled()
    expect(mockNavigate).not.toHaveBeenCalled()
  })

  // ── firstAttemptSuccessRate (speak mode) ───────────────────────────────────

  it("shows first-attempt success rate when prop is provided", () => {
    render(
      <SessionSummary
        cardsReviewed={5}
        recallRate={0.8}
        nextDue={null}
        firstAttemptSuccessRate={0.75}
      />
    )
    expect(screen.getByText(/first-attempt success: 75%/i)).toBeInTheDocument()
  })

  it("does NOT show first-attempt success rate when prop is undefined", () => {
    render(
      <SessionSummary
        cardsReviewed={5}
        recallRate={0.8}
        nextDue={null}
      />
    )
    expect(screen.queryByText(/first-attempt success/i)).not.toBeInTheDocument()
  })

  it("rounds first-attempt success rate to nearest integer percent", () => {
    render(
      <SessionSummary
        cardsReviewed={3}
        recallRate={1.0}
        nextDue={null}
        firstAttemptSuccessRate={1 / 3}
      />
    )
    expect(screen.getByText(/first-attempt success: 33%/i)).toBeInTheDocument()
  })
})
