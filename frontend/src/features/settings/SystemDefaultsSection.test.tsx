/**
 * SystemDefaultsSection component tests — TDD (written BEFORE implementation).
 *
 * Tests cover: rendering system defaults, saving.
 *
 * AC6
 */

import React from "react"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { SystemDefaultsSection } from "./SystemDefaultsSection"

vi.mock("@/lib/client", () => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
  patch: vi.fn(),
  ApiError: class ApiError extends Error {
    status: number
    type: string
    title: string
    detail?: string
    constructor(status: number, type: string, title: string, detail?: string) {
      super(title)
      this.name = "ApiError"
      this.status = status
      this.type = type
      this.title = title
      this.detail = detail
    }
  },
}))

import { get, put } from "@/lib/client"

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
}

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={makeQueryClient()}>{children}</QueryClientProvider>
  )
}

const MOCK_SETTINGS = {
  id: 1,
  native_language: "en",
  active_target_language: "es",
  target_languages: '["es"]',
  auto_generate_audio: true,
  auto_generate_images: false,
  default_practice_mode: "self_assess",
  cards_per_session: 20,
  onboarding_completed: true,
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(get).mockResolvedValue(MOCK_SETTINGS)
  vi.mocked(put).mockResolvedValue(MOCK_SETTINGS)
})

describe("SystemDefaultsSection", () => {
  it("renders auto_generate_audio and auto_generate_images toggles", async () => {
    render(
      <Wrapper>
        <SystemDefaultsSection />
      </Wrapper>
    )
    await waitFor(() => {
      const text = document.body.textContent ?? ""
      expect(text).toMatch(/audio/i)
      expect(text).toMatch(/image/i)
    })
  })

  it("renders default_practice_mode select with 3 options", async () => {
    render(
      <Wrapper>
        <SystemDefaultsSection />
      </Wrapper>
    )
    await waitFor(() => {
      const select = screen.getByRole("combobox")
      const options = select.querySelectorAll("option")
      expect(options.length).toBeGreaterThanOrEqual(3)
    })
  })

  it("renders cards_per_session number input with min=1, max=100", async () => {
    render(
      <Wrapper>
        <SystemDefaultsSection />
      </Wrapper>
    )
    await waitFor(() => {
      const input = screen.getByRole("spinbutton")
      expect(input).toHaveAttribute("min", "1")
      expect(input).toHaveAttribute("max", "100")
    })
  })

  it("Save is disabled when no fields have changed (dirty tracking)", async () => {
    render(
      <Wrapper>
        <SystemDefaultsSection />
      </Wrapper>
    )
    // Wait for settings to load and form to sync
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /save/i })).toBeDisabled()
    })
  })

  it("Save becomes enabled after changing a field", async () => {
    const user = userEvent.setup()
    render(
      <Wrapper>
        <SystemDefaultsSection />
      </Wrapper>
    )
    // Wait for settings to load — confirmed when Save is disabled (isDirty=false)
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /save/i })).toBeDisabled()
    })
    // Toggle the audio switch (MOCK has auto_generate_audio=true → click → false)
    const audioSwitch = screen.getByLabelText("Auto-generate audio")
    await user.click(audioSwitch)
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /save/i })).not.toBeDisabled()
    })
  })

  it("'Unsaved changes' indicator appears when form is dirty", async () => {
    const user = userEvent.setup()
    render(
      <Wrapper>
        <SystemDefaultsSection />
      </Wrapper>
    )
    // Wait for settings to load first
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /save/i })).toBeDisabled()
    })
    // Toggle the audio switch (MOCK has auto_generate_audio=true → click → false)
    const audioSwitch = screen.getByLabelText("Auto-generate audio")
    await user.click(audioSwitch)
    await waitFor(() => {
      expect(screen.getByText(/unsaved changes/i)).toBeInTheDocument()
    })
  })

  it("Save calls PUT /settings with ONLY dirty fields", async () => {
    const user = userEvent.setup()
    render(
      <Wrapper>
        <SystemDefaultsSection />
      </Wrapper>
    )
    // Wait for settings to load (button disabled = settings loaded, isDirty=false)
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /save/i })).toBeDisabled()
    })
    // Toggle only auto_generate_audio — all other fields stay at MOCK values
    // MOCK: auto_generate_audio=true → click → false
    const audioSwitch = screen.getByLabelText("Auto-generate audio")
    await user.click(audioSwitch)
    // Wait for Save to become enabled
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /save/i })).not.toBeDisabled()
    })
    await user.click(screen.getByRole("button", { name: /save/i }))
    await waitFor(() => {
      expect(vi.mocked(put)).toHaveBeenCalledWith(
        "/settings",
        // Only the changed field should be sent
        expect.objectContaining({ auto_generate_audio: false })
      )
      // Unchanged fields should NOT be in the payload
      const callArg = vi.mocked(put).mock.calls[0][1] as Record<string, unknown>
      expect(callArg).not.toHaveProperty("auto_generate_images")
      expect(callArg).not.toHaveProperty("default_practice_mode")
      expect(callArg).not.toHaveProperty("cards_per_session")
    })
  })
})
