/**
 * SystemDefaultsSection component tests — TDD (written BEFORE implementation).
 *
 * Tests cover: rendering system defaults, saving.
 *
 * AC6
 */

import React from "react"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
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

  it("Save calls PUT /settings", async () => {
    render(
      <Wrapper>
        <SystemDefaultsSection />
      </Wrapper>
    )
    await waitFor(() => {
      const text = document.body.textContent ?? ""
      expect(text).toMatch(/audio|image|session/i)
    })
    const saveBtn = screen.getByRole("button", { name: /save/i })
    fireEvent.click(saveBtn)
    await waitFor(() => {
      expect(vi.mocked(put)).toHaveBeenCalledWith("/settings", expect.any(Object))
    })
  })
})
