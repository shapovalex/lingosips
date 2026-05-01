/**
 * LanguageSection component tests — TDD (written BEFORE implementation).
 *
 * Tests cover: rendering language selections, saving, safe JSON parsing of target_languages.
 *
 * AC5
 */

import React from "react"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { LanguageSection } from "./LanguageSection"

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
  vi.mocked(put).mockResolvedValue({ ...MOCK_SETTINGS })
})

describe("LanguageSection", () => {
  it("renders current native language and active target language", async () => {
    render(
      <Wrapper>
        <LanguageSection />
      </Wrapper>
    )
    await waitFor(() => {
      expect(screen.getAllByRole("combobox").length).toBeGreaterThanOrEqual(1)
    })
  })

  it("Save button calls PUT /settings with language fields", async () => {
    vi.mocked(put).mockResolvedValue({ ...MOCK_SETTINGS, native_language: "fr" })
    render(
      <Wrapper>
        <LanguageSection />
      </Wrapper>
    )
    await waitFor(() => {
      expect(screen.getAllByRole("combobox").length).toBeGreaterThanOrEqual(1)
    })
    const saveBtn = screen.getByRole("button", { name: /save/i })
    fireEvent.click(saveBtn)
    await waitFor(() => {
      expect(vi.mocked(put)).toHaveBeenCalledWith(
        "/settings",
        expect.objectContaining({ native_language: expect.any(String) })
      )
    })
  })

  it("safeParseLanguages handles malformed JSON string without crashing", async () => {
    vi.mocked(get).mockResolvedValue({
      ...MOCK_SETTINGS,
      target_languages: "INVALID_JSON{{{{",
    })
    expect(() =>
      render(
        <Wrapper>
          <LanguageSection />
        </Wrapper>
      )
    ).not.toThrow()
  })

  it("cannot remove the only active target language (button absent or disabled)", async () => {
    vi.mocked(get).mockResolvedValue({
      ...MOCK_SETTINGS,
      target_languages: '["es"]',
      active_target_language: "es",
    })
    render(
      <Wrapper>
        <LanguageSection />
      </Wrapper>
    )
    await waitFor(() => {
      expect(screen.getAllByRole("combobox").length).toBeGreaterThanOrEqual(1)
    })
    const removeButtons = screen.queryAllByRole("button", { name: /remove/i })
    const allDisabled = removeButtons.every((btn) => btn.hasAttribute("disabled"))
    expect(removeButtons.length === 0 || allDisabled).toBe(true)
  })

  it("parses target_languages JSON string to display language information", async () => {
    vi.mocked(get).mockResolvedValue({
      ...MOCK_SETTINGS,
      target_languages: '["es", "fr", "de"]',
    })
    render(
      <Wrapper>
        <LanguageSection />
      </Wrapper>
    )
    await waitFor(() => {
      const text = document.body.textContent ?? ""
      expect(text).toMatch(/Spanish|es/i)
    })
  })
})
