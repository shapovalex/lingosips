/**
 * useImportProgress hook tests — TDD (written before implementation).
 *
 * Tests cover SSE event handling for GET /import/{job_id}/progress.
 * Uses fake EventSource via vi.stubGlobal.
 */

import { renderHook, act } from "@testing-library/react"
import { vi, describe, it, expect, beforeEach, afterEach } from "vitest"
import { useImportProgress } from "./useImportProgress"

// ── Fake EventSource implementation ──────────────────────────────────────────

class FakeEventSource {
  static instances: FakeEventSource[] = []
  url: string
  listeners: Map<string, ((e: MessageEvent) => void)[]> = new Map()
  closed = false

  constructor(url: string) {
    this.url = url
    FakeEventSource.instances.push(this)
  }

  addEventListener(type: string, handler: (e: MessageEvent) => void) {
    if (!this.listeners.has(type)) this.listeners.set(type, [])
    this.listeners.get(type)!.push(handler)
  }

  removeEventListener(_type: string, _handler: (e: MessageEvent) => void) {
    // Not needed for these tests
  }

  close() {
    this.closed = true
  }

  emit(type: string, data: unknown) {
    const event = { data: JSON.stringify(data) } as MessageEvent
    for (const handler of this.listeners.get(type) ?? []) {
      handler(event)
    }
  }
}

// ── Mock useAppStore ──────────────────────────────────────────────────────────

const mockSetImportProgress = vi.fn()
const mockAddNotification = vi.fn()
const mockSetActiveImportJobId = vi.fn()

const mockStore = {
  importProgress: {
    done: 0, total: 0, currentItem: null, status: "idle" as const,
    enriched: 0, unresolved: 0, errorMessage: null,
  },
  setImportProgress: mockSetImportProgress,
  addNotification: mockAddNotification,
  setActiveImportJobId: mockSetActiveImportJobId,
}

vi.mock("@/lib/stores/useAppStore", () => ({
  useAppStore: Object.assign(
    (selector: (s: typeof mockStore) => unknown) => selector(mockStore),
    { getState: () => mockStore }
  ),
}))

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("useImportProgress", () => {
  beforeEach(() => {
    FakeEventSource.instances = []
    vi.stubGlobal("EventSource", FakeEventSource)
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("returns idle progress when jobId is null", () => {
    const { result } = renderHook(() => useImportProgress(null))
    expect(result.current.status).toBe("idle")
    expect(result.current.done).toBe(0)
  })

  it("creates EventSource when jobId is provided", () => {
    renderHook(() => useImportProgress(42))
    expect(FakeEventSource.instances).toHaveLength(1)
    expect(FakeEventSource.instances[0].url).toBe("/import/42/progress")
  })

  it("sets status=running on progress SSE events", () => {
    renderHook(() => useImportProgress(42))
    const es = FakeEventSource.instances[0]

    act(() => {
      es.emit("progress", { done: 5, total: 10, current_item: "enriching 'hola'..." })
    })

    expect(mockSetImportProgress).toHaveBeenCalledWith(
      expect.objectContaining({ done: 5, total: 10, status: "running" })
    )
  })

  it("sets status=complete on complete SSE event", () => {
    renderHook(() => useImportProgress(42))
    const es = FakeEventSource.instances[0]

    act(() => {
      es.emit("complete", { enriched: 8, unresolved: 2 })
    })

    expect(mockSetImportProgress).toHaveBeenCalledWith(
      expect.objectContaining({ status: "complete", enriched: 8, unresolved: 2 })
    )
  })

  it("fires addNotification on complete event", () => {
    renderHook(() => useImportProgress(42))
    const es = FakeEventSource.instances[0]

    act(() => {
      es.emit("complete", { enriched: 8, unresolved: 2 })
    })

    expect(mockAddNotification).toHaveBeenCalledWith(
      expect.objectContaining({ type: "success" })
    )
  })

  it("cleans up EventSource on unmount", () => {
    const { unmount } = renderHook(() => useImportProgress(42))
    const es = FakeEventSource.instances[0]

    unmount()

    expect(es.closed).toBe(true)
  })
})
