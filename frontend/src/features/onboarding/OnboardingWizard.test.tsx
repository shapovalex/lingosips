/**
 * OnboardingWizard component tests — TDD (written before component implementation).
 *
 * Tests cover all states of the WizardState machine:
 *   "idle" → "submitting" → success (wizard unmounts via query invalidation)
 *   "idle" → "submitting" → "error" → "idle" (retry)
 *
 * Accessibility (UX-DR13): role="main", aria-label, aria-live, Tab order.
 */

import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { vi, describe, it, expect, beforeEach } from "vitest"
import { OnboardingWizard } from "./OnboardingWizard"
import * as client from "@/lib/client"

function renderWizard() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return {
    ...render(
      <QueryClientProvider client={queryClient}>
        <OnboardingWizard />
      </QueryClientProvider>
    ),
    queryClient,
  }
}

describe("OnboardingWizard", () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  // ── Idle state ──────────────────────────────────────────────────────────────

  it("renders in idle state with native and target selects and both buttons", () => {
    renderWizard()
    expect(screen.getByLabelText("Native language")).toBeInTheDocument()
    expect(screen.getByLabelText("Target language")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Start learning" })).toBeEnabled()
    expect(screen.getByRole("button", { name: "Skip for now" })).toBeEnabled()
  })

  it("has correct accessibility attributes on the container", () => {
    renderWizard()
    expect(screen.getByRole("main", { name: "Language setup" })).toBeInTheDocument()
  })

  it("has aria-live region for error announcements", () => {
    renderWizard()
    // The aria-live="polite" region should exist in idle state (no alert content yet)
    const liveRegion = document.querySelector('[aria-live="polite"]')
    expect(liveRegion).toBeTruthy()
  })

  it("native select defaults to English (en)", () => {
    renderWizard()
    const nativeSelect = screen.getByLabelText("Native language") as HTMLSelectElement
    expect(nativeSelect.value).toBe("en")
  })

  it("target select defaults to Spanish (es)", () => {
    renderWizard()
    const targetSelect = screen.getByLabelText("Target language") as HTMLSelectElement
    expect(targetSelect.value).toBe("es")
  })

  // ── Submitting state ────────────────────────────────────────────────────────

  it("disables inputs and shows 'Starting...' during submission", async () => {
    vi.spyOn(client, "put").mockImplementation(() => new Promise(() => {})) // never resolves
    renderWizard()
    fireEvent.click(screen.getByRole("button", { name: "Start learning" }))

    await waitFor(() => {
      expect(screen.getByLabelText("Native language")).toBeDisabled()
      expect(screen.getByLabelText("Target language")).toBeDisabled()
      expect(screen.getByRole("button", { name: "Starting..." })).toBeDisabled()
    })
  })

  it("hides 'Skip for now' during submission", async () => {
    vi.spyOn(client, "put").mockImplementation(() => new Promise(() => {}))
    renderWizard()
    fireEvent.click(screen.getByRole("button", { name: "Start learning" }))

    await waitFor(() => {
      expect(screen.queryByRole("button", { name: "Skip for now" })).not.toBeInTheDocument()
    })
  })

  // ── Start learning — success ────────────────────────────────────────────────

  it("calls PUT /settings with selected languages and onboarding_completed=true", async () => {
    const mockPut = vi.spyOn(client, "put").mockResolvedValue({})
    renderWizard()

    // Change target language to French
    fireEvent.change(screen.getByLabelText("Target language"), { target: { value: "fr" } })
    fireEvent.click(screen.getByRole("button", { name: "Start learning" }))

    await waitFor(() => {
      expect(mockPut).toHaveBeenCalledWith("/settings", {
        native_language: "en",
        active_target_language: "fr",
        onboarding_completed: true,
      })
    })
  })

  // ── Skip — sends defaults ───────────────────────────────────────────────────

  it("skip sends default languages with onboarding_completed=true", async () => {
    const mockPut = vi.spyOn(client, "put").mockResolvedValue({})
    renderWizard()

    // Even if user changed something, skip uses defaults
    fireEvent.change(screen.getByLabelText("Native language"), { target: { value: "fr" } })
    fireEvent.click(screen.getByRole("button", { name: "Skip for now" }))

    await waitFor(() => {
      expect(mockPut).toHaveBeenCalledWith("/settings", {
        native_language: "en",
        active_target_language: "es",
        onboarding_completed: true,
      })
    })
  })

  // ── Error state ─────────────────────────────────────────────────────────────

  it("shows error alert when PUT fails", async () => {
    vi.spyOn(client, "put").mockRejectedValue(new Error("Network error"))
    renderWizard()
    fireEvent.click(screen.getByRole("button", { name: "Start learning" }))

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument()
    })
  })

  it("shows 'Try again' button in error state", async () => {
    vi.spyOn(client, "put").mockRejectedValue(new Error("Server unavailable"))
    renderWizard()
    fireEvent.click(screen.getByRole("button", { name: "Start learning" }))

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Try again" })).toBeEnabled()
    })
  })

  it("error message includes the error detail (UX-DR13)", async () => {
    vi.spyOn(client, "put").mockRejectedValue(new Error("Connection refused"))
    renderWizard()
    fireEvent.click(screen.getByRole("button", { name: "Start learning" }))

    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toContain("Connection refused")
    })
  })

  it("retry clears error and re-enables the form (idle state)", async () => {
    vi.spyOn(client, "put").mockRejectedValue(new Error("Network error"))
    renderWizard()
    fireEvent.click(screen.getByRole("button", { name: "Start learning" }))

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Try again" })).toBeEnabled()
    })

    fireEvent.click(screen.getByRole("button", { name: "Try again" }))

    await waitFor(() => {
      // Error alert gone, "Start learning" back
      expect(screen.queryByRole("alert")).not.toBeInTheDocument()
      expect(screen.getByRole("button", { name: "Start learning" })).toBeEnabled()
      expect(screen.getByLabelText("Native language")).not.toBeDisabled()
    })
  })
})
