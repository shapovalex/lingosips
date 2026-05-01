/**
 * useCardStream hook tests — TDD (written before implementation).
 *
 * Tests drive the CardCreationState machine:
 *   idle → loading → populated  (successful stream)
 *   idle → loading → error      (SSE error event)
 *   idle → loading → error      (streamPost throws ApiError)
 *   populated → idle             (after saveCard)
 *   populated → idle             (after discard)
 *   error → idle                 (after reset)
 *
 * Mock: streamPost is mocked via vi.mock("../../lib/client")
 * Wrapper: QueryClientProvider required for useQueryClient()
 */

import { renderHook, act, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { vi, describe, it, expect, beforeEach, afterEach } from "vitest"
import React from "react"
import { useCardStream } from "./useCardStream"
import { ApiError } from "../../lib/client"

// ── Mock streamPost ──────────────────────────────────────────────────────────
vi.mock("../../lib/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../lib/client")>()
  return {
    ...actual,
    streamPost: vi.fn(),
  }
})

import { streamPost } from "../../lib/client"
const mockStreamPost = vi.mocked(streamPost)

// ── Helpers ──────────────────────────────────────────────────────────────────

/** Build an async generator from pre-defined events */
async function* makeEventStream(
  events: Array<{ event: string; data: unknown }>
) {
  for (const e of events) {
    yield e as import("../../lib/client").SseEvent
  }
}

/** Create a wrapper with QueryClientProvider */
function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  afterEach(() => queryClient.clear())

  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: queryClient }, children)
  }
}

// ── Tests ────────────────────────────────────────────────────────────────────

describe("useCardStream", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useRealTimers() // ensure real timers before each test (guards against fake timer leaks)
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  // ── Initial state ──────────────────────────────────────────────────────────

  it("starts in idle state with empty fields and no error", () => {
    const wrapper = createWrapper()
    const { result } = renderHook(() => useCardStream(), { wrapper })

    expect(result.current.state).toBe("idle")
    expect(result.current.fields).toEqual({})
    expect(result.current.errorMessage).toBeNull()
  })

  // ── loading → populated (successful stream) ────────────────────────────────

  it("transitions loading → populated and accumulates fields on success", async () => {
    const wrapper = createWrapper()
    mockStreamPost.mockImplementation(() =>
      makeEventStream([
        { event: "field_update", data: { field: "translation", value: "sad" } },
        {
          event: "field_update",
          data: {
            field: "forms",
            value: { gender: null, article: null, plural: null, conjugations: {} },
          },
        },
        {
          event: "field_update",
          data: { field: "example_sentences", value: ["She was sad.", "A sad day."] },
        },
        { event: "field_update", data: { field: "audio", value: "/cards/1/audio" } },
        { event: "complete", data: { card_id: 1 } },
      ])
    )

    const { result } = renderHook(() => useCardStream(), { wrapper })

    act(() => {
      result.current.startStream("triste")
    })

    // Should enter loading immediately
    expect(result.current.state).toBe("loading")

    await waitFor(() => expect(result.current.state).toBe("populated"))

    expect(result.current.fields.translation).toBe("sad")
    expect(result.current.fields.forms).toEqual({
      gender: null,
      article: null,
      plural: null,
      conjugations: {},
    })
    expect(result.current.fields.example_sentences).toEqual(["She was sad.", "A sad day."])
    expect(result.current.fields.audio).toBe("/cards/1/audio")
    expect(result.current.fields.card_id).toBe(1)
    expect(result.current.errorMessage).toBeNull()
  })

  it("calls streamPost with correct path and target_word body", async () => {
    const wrapper = createWrapper()
    mockStreamPost.mockImplementation(() =>
      makeEventStream([{ event: "complete", data: { card_id: 7 } }])
    )

    const { result } = renderHook(() => useCardStream(), { wrapper })

    act(() => {
      result.current.startStream("melancholic")
    })

    await waitFor(() => expect(result.current.state).toBe("populated"))

    expect(mockStreamPost).toHaveBeenCalledWith(
      "/cards/stream",
      { target_word: "melancholic" },
      expect.any(AbortSignal)
    )
  })

  // ── loading → error (SSE error event) ─────────────────────────────────────

  it("transitions loading → error on SSE error event", async () => {
    const wrapper = createWrapper()
    mockStreamPost.mockImplementation(() =>
      makeEventStream([
        { event: "field_update", data: { field: "translation", value: "test" } },
        { event: "error", data: { message: "Local Qwen timeout after 10s" } },
      ])
    )

    const { result } = renderHook(() => useCardStream(), { wrapper })

    act(() => {
      result.current.startStream("test")
    })

    await waitFor(() => expect(result.current.state).toBe("error"))

    expect(result.current.errorMessage).toBe("Local Qwen timeout after 10s")
    // Partial fields should not be shown in error state
    expect(result.current.state).toBe("error")
  })

  // ── loading → error (thrown ApiError) ────────────────────────────────────

  it("transitions loading → error when streamPost throws ApiError", async () => {
    const wrapper = createWrapper()
    // eslint-disable-next-line require-yield
    mockStreamPost.mockImplementation(async function* () {
      throw new ApiError(503, "/errors/503", "Service Unavailable", "LLM offline")
    })

    const { result } = renderHook(() => useCardStream(), { wrapper })

    act(() => {
      result.current.startStream("word")
    })

    await waitFor(() => expect(result.current.state).toBe("error"))

    expect(result.current.errorMessage).toBe("Service Unavailable")
  })

  it("uses err.message for non-ApiError throws (more specific than generic fallback)", async () => {
    // When streamPost re-throws a non-ApiError (e.g. network reset), useCardStream
    // uses err.message to give a more specific error than the old "Connection failed" default.
    const wrapper = createWrapper()
    // eslint-disable-next-line require-yield
    mockStreamPost.mockImplementation(async function* () {
      throw new Error("Network error")
    })

    const { result } = renderHook(() => useCardStream(), { wrapper })

    act(() => {
      result.current.startStream("word")
    })

    await waitFor(() => expect(result.current.state).toBe("error"))

    // err.message ("Network error") is used — not the old generic "Connection failed"
    expect(result.current.errorMessage).toBe("Network error")
  })

  // ── populated → idle (saveCard) ────────────────────────────────────────────

  it("transitions populated → saving → idle after saveCard()", async () => {
    const wrapper = createWrapper()
    mockStreamPost.mockImplementation(() =>
      makeEventStream([{ event: "complete", data: { card_id: 5 } }])
    )

    const { result } = renderHook(() => useCardStream(), { wrapper })

    act(() => {
      result.current.startStream("hello")
    })

    await waitFor(() => expect(result.current.state).toBe("populated"))

    act(() => {
      result.current.saveCard()
    })

    // Should immediately transition to saving
    expect(result.current.state).toBe("saving")

    // Wait for the 300ms setTimeout to fire (using real timers)
    await waitFor(() => expect(result.current.state).toBe("idle"), { timeout: 2000 })

    expect(result.current.fields).toEqual({})
    expect(result.current.errorMessage).toBeNull()
  })

  // ── populated → idle (discard) ─────────────────────────────────────────────

  it("resets all state to idle on discard()", async () => {
    const wrapper = createWrapper()
    mockStreamPost.mockImplementation(() =>
      makeEventStream([
        { event: "field_update", data: { field: "translation", value: "test" } },
        { event: "complete", data: { card_id: 3 } },
      ])
    )

    const { result } = renderHook(() => useCardStream(), { wrapper })

    act(() => {
      result.current.startStream("test")
    })

    await waitFor(() => expect(result.current.state).toBe("populated"))

    act(() => {
      result.current.discard()
    })

    expect(result.current.state).toBe("idle")
    expect(result.current.fields).toEqual({})
    expect(result.current.errorMessage).toBeNull()
  })

  // ── error → idle (reset) ───────────────────────────────────────────────────

  it("returns to idle from error state on reset()", async () => {
    const wrapper = createWrapper()
    mockStreamPost.mockImplementation(() =>
      makeEventStream([{ event: "error", data: { message: "Timeout" } }])
    )

    const { result } = renderHook(() => useCardStream(), { wrapper })

    act(() => {
      result.current.startStream("word")
    })

    await waitFor(() => expect(result.current.state).toBe("error"))

    act(() => {
      result.current.reset()
    })

    expect(result.current.state).toBe("idle")
    expect(result.current.errorMessage).toBeNull()
  })

  // ── signal.aborted mid-loop guard (line 55 branch) ────────────────────────

  it("stops state updates when signal is aborted mid-stream (signal.aborted guard)", async () => {
    const wrapper = createWrapper()

    // A stream that:
    // 1. yields field_update
    // 2. waits for abort signal
    // 3. yields complete event WHILE signal is already aborted
    // → line 55 check should fire and prevent "populated" state
    mockStreamPost.mockImplementation(async function* (_path, _body, signal) {
      yield { event: "field_update" as const, data: { field: "translation", value: "test" } }
      // Block until signal is aborted
      await new Promise<void>((resolve) => {
        signal?.addEventListener("abort", () => resolve())
      })
      // Signal is now aborted — yield complete anyway to exercise line 55 guard
      yield { event: "complete" as const, data: { card_id: 99 } }
    })

    const { result } = renderHook(() => useCardStream(), { wrapper })

    act(() => {
      result.current.startStream("test")
    })

    // Wait for the first event to be processed (translation field set)
    await waitFor(() => expect(result.current.fields.translation).toBe("test"))

    // Abort via discard() — signal.aborted becomes true, generator unblocks and yields complete
    act(() => {
      result.current.discard()
    })

    // State should be idle (discard reset it); the "complete" event was ignored by line 55 guard
    await waitFor(() => expect(result.current.state).toBe("idle"))
    expect(result.current.fields).toEqual({})
  })

  // ── unrecognized event type (else-if fall-through) ─────────────────────────

  it("ignores unrecognized event types (e.g. progress events) without state change", async () => {
    const wrapper = createWrapper()

    mockStreamPost.mockImplementation(() =>
      makeEventStream([
        { event: "progress" as "field_update", data: { done: 1, total: 10 } },
        { event: "complete", data: { card_id: 5 } },
      ])
    )

    const { result } = renderHook(() => useCardStream(), { wrapper })

    act(() => {
      result.current.startStream("word")
    })

    // Progress events are silently ignored; complete transitions to populated
    await waitFor(() => expect(result.current.state).toBe("populated"))
    expect(result.current.fields.card_id).toBe(5)
  })

  // ── signal.aborted in catch block (line 71 branch) ────────────────────────

  it("does not set error state when throw is caused by abort (signal.aborted catch guard)", async () => {
    const wrapper = createWrapper()

    // Generator blocks until aborted, then throws AbortError — simulating native fetch behavior
    // eslint-disable-next-line require-yield
    mockStreamPost.mockImplementation(async function* (_path, _body, signal) {
      await new Promise<void>((_, reject) => {
        // When signal is aborted, throw AbortError
        signal?.addEventListener("abort", () =>
          reject(new DOMException("The operation was aborted", "AbortError"))
        )
      })
    })

    const { result } = renderHook(() => useCardStream(), { wrapper })

    act(() => {
      result.current.startStream("word")
    })

    expect(result.current.state).toBe("loading")

    // Abort the stream via discard — this sets signal.aborted=true AND triggers the AbortError
    act(() => {
      result.current.discard()
    })

    // State should be idle (discard reset it), and error should NOT override it
    // because the catch block returns early when signal.aborted is true
    await waitFor(() => expect(result.current.state).toBe("idle"))
    expect(result.current.errorMessage).toBeNull()
  })

  // ── Abort on new startStream call ──────────────────────────────────────────

  it("aborts previous in-flight stream when startStream is called again", async () => {
    const wrapper = createWrapper()

    // First stream never completes
    let resolveFirst: (() => void) | null = null
    mockStreamPost
      // eslint-disable-next-line require-yield
      .mockImplementationOnce(async function* () {
        await new Promise<void>((resolve) => {
          resolveFirst = resolve
        })
        // Never yields — just blocks
      })
      .mockImplementationOnce(() =>
        makeEventStream([{ event: "complete", data: { card_id: 10 } }])
      )

    const { result } = renderHook(() => useCardStream(), { wrapper })

    act(() => {
      result.current.startStream("first")
    })

    expect(result.current.state).toBe("loading")

    // Start second stream — should abort first
    act(() => {
      result.current.startStream("second")
    })

    // Resolve first stream (but it should be ignored since aborted)
    // resolveFirst is assigned inside the mock closure; cast to override TypeScript CFA narrowing.
    ;(resolveFirst as (() => void) | null)?.call(null)

    await waitFor(() => expect(result.current.state).toBe("populated"))

    expect(result.current.fields.card_id).toBe(10)
    expect(mockStreamPost).toHaveBeenCalledTimes(2)
  })
})
