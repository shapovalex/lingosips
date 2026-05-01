/**
 * AIServicePanel component tests — TDD (written BEFORE implementation).
 *
 * Tests cover all state machine transitions:
 *   closed → open-form → testing → test-success → saving → configured
 *   closed → open-form → testing → test-error
 *
 * AC1, AC2, AC3, AC4
 */

import React from "react"
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { AIServicePanel } from "./AIServicePanel"

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

import { get, post, del } from "@/lib/client"

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

beforeEach(() => {
  vi.clearAllMocks()
})

describe("AIServicePanel", () => {
  it("renders 'Local Qwen — active' and Upgrade button when not configured", async () => {
    vi.mocked(get).mockResolvedValue({
      llm: { provider: "qwen_local", model: null },
      speech: { provider: "pyttsx3" },
    })
    render(
      <Wrapper>
        <AIServicePanel />
      </Wrapper>
    )
    await screen.findByText(/local qwen/i)
    expect(screen.getByRole("button", { name: /upgrade/i })).toBeInTheDocument()
  })

  it("renders 'OpenRouter · model — active' and Remove button when configured", async () => {
    vi.mocked(get).mockResolvedValue({
      llm: { provider: "openrouter", model: "openai/gpt-4o-mini" },
      speech: { provider: "pyttsx3" },
    })
    render(
      <Wrapper>
        <AIServicePanel />
      </Wrapper>
    )
    await screen.findByText(/openrouter/i)
    expect(screen.getByRole("button", { name: /remove/i })).toBeInTheDocument()
  })

  it("clicking Upgrade reveals form inline — no modal dialog", async () => {
    vi.mocked(get).mockResolvedValue({
      llm: { provider: "qwen_local", model: null },
      speech: { provider: "pyttsx3" },
    })
    render(
      <Wrapper>
        <AIServicePanel />
      </Wrapper>
    )
    const upgradeBtn = await screen.findByRole("button", { name: /upgrade/i })
    fireEvent.click(upgradeBtn)
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    expect(screen.getByLabelText(/api key/i)).toBeInTheDocument()
  })

  it("form shows OpenRouter signup link (AC1)", async () => {
    vi.mocked(get).mockResolvedValue({
      llm: { provider: "qwen_local", model: null },
      speech: { provider: "pyttsx3" },
    })
    render(
      <Wrapper>
        <AIServicePanel />
      </Wrapper>
    )
    const upgradeBtn = await screen.findByRole("button", { name: /upgrade/i })
    fireEvent.click(upgradeBtn)
    const signupLink = screen.getByRole("link", { name: /sign up for openrouter/i })
    expect(signupLink).toBeInTheDocument()
    expect(signupLink).toHaveAttribute("href", "https://openrouter.ai/keys")
  })

  it("api_key input has type='password'", async () => {
    vi.mocked(get).mockResolvedValue({
      llm: { provider: "qwen_local", model: null },
      speech: { provider: "pyttsx3" },
    })
    render(
      <Wrapper>
        <AIServicePanel />
      </Wrapper>
    )
    const upgradeBtn = await screen.findByRole("button", { name: /upgrade/i })
    fireEvent.click(upgradeBtn)
    const keyInput = screen.getByLabelText(/api key/i)
    expect(keyInput).toHaveAttribute("type", "password")
  })

  it("'Test connection' button is disabled when api_key is empty", async () => {
    vi.mocked(get).mockResolvedValue({
      llm: { provider: "qwen_local", model: null },
      speech: { provider: "pyttsx3" },
    })
    render(
      <Wrapper>
        <AIServicePanel />
      </Wrapper>
    )
    const upgradeBtn = await screen.findByRole("button", { name: /upgrade/i })
    fireEvent.click(upgradeBtn)
    const testBtn = screen.getByRole("button", { name: /test connection/i })
    expect(testBtn).toBeDisabled()
  })

  it("test-success state shows sample_translation and active Save button", async () => {
    vi.mocked(get).mockResolvedValue({
      llm: { provider: "qwen_local", model: null },
      speech: { provider: "pyttsx3" },
    })
    vi.mocked(post).mockResolvedValue({
      success: true,
      sample_translation: "hola",
      error_code: null,
      error_message: null,
    })
    render(
      <Wrapper>
        <AIServicePanel />
      </Wrapper>
    )
    const upgradeBtn = await screen.findByRole("button", { name: /upgrade/i })
    fireEvent.click(upgradeBtn)
    fireEvent.change(screen.getByLabelText(/api key/i), {
      target: { value: "sk-valid-key" },
    })
    const select = screen.getByRole("combobox")
    fireEvent.change(select, { target: { value: "openai/gpt-4o-mini" } })
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /test connection/i }))
    })
    await screen.findByTestId("test-success-message", undefined, { timeout: 3000 })
    const saveBtn = screen.getByRole("button", { name: /save/i })
    expect(saveBtn).not.toBeDisabled()
  })

  it("test-error shows 'Invalid API key' message and no Save button", async () => {
    vi.mocked(get).mockResolvedValue({
      llm: { provider: "qwen_local", model: null },
      speech: { provider: "pyttsx3" },
    })
    vi.mocked(post).mockResolvedValue({
      success: false,
      sample_translation: null,
      error_code: "invalid_api_key",
      error_message: "Invalid API key · Check your OpenRouter dashboard",
    })
    render(
      <Wrapper>
        <AIServicePanel />
      </Wrapper>
    )
    const upgradeBtn = await screen.findByRole("button", { name: /upgrade/i })
    fireEvent.click(upgradeBtn)
    fireEvent.change(screen.getByLabelText(/api key/i), {
      target: { value: "sk-bad" },
    })
    const select = screen.getByRole("combobox")
    fireEvent.change(select, { target: { value: "openai/gpt-4o-mini" } })
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /test connection/i }))
    })
    await screen.findByTestId("test-error-message", undefined, { timeout: 3000 })
    expect(screen.getByTestId("test-error-message")).toHaveTextContent(/invalid api key/i)
    expect(screen.queryByRole("button", { name: /^save$/i })).not.toBeInTheDocument()
  })

  it("Save calls POST /services/credentials", async () => {
    vi.mocked(get).mockResolvedValue({
      llm: { provider: "qwen_local", model: null },
      speech: { provider: "pyttsx3" },
    })
    vi.mocked(post)
      .mockResolvedValueOnce({
        success: true,
        sample_translation: "hola",
        error_code: null,
        error_message: null,
      })
      .mockResolvedValueOnce({ saved: true })
    render(
      <Wrapper>
        <AIServicePanel />
      </Wrapper>
    )
    const upgradeBtn = await screen.findByRole("button", { name: /upgrade/i })
    fireEvent.click(upgradeBtn)
    fireEvent.change(screen.getByLabelText(/api key/i), {
      target: { value: "sk-valid" },
    })
    const select = screen.getByRole("combobox")
    fireEvent.change(select, { target: { value: "openai/gpt-4o-mini" } })
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /test connection/i }))
    })
    await screen.findByTestId("test-success-message", undefined, { timeout: 3000 })
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /save/i }))
    })
    await waitFor(() => {
      expect(vi.mocked(post)).toHaveBeenCalledWith(
        "/services/credentials",
        expect.objectContaining({ openrouter_api_key: "sk-valid" })
      )
    })
  })

  it("Remove calls DELETE /services/credentials/openrouter", async () => {
    vi.mocked(get).mockResolvedValue({
      llm: { provider: "openrouter", model: "openai/gpt-4o-mini" },
      speech: { provider: "pyttsx3" },
    })
    vi.mocked(del).mockResolvedValue(undefined)
    render(
      <Wrapper>
        <AIServicePanel />
      </Wrapper>
    )
    const removeBtn = await screen.findByRole("button", { name: /remove/i })
    fireEvent.click(removeBtn)
    await waitFor(() => {
      expect(vi.mocked(del)).toHaveBeenCalledWith("/services/credentials/openrouter")
    })
  })

  it("has aria-live region for state change announcements", async () => {
    vi.mocked(get).mockResolvedValue({
      llm: { provider: "qwen_local", model: null },
      speech: { provider: "pyttsx3" },
    })
    const { container } = render(
      <Wrapper>
        <AIServicePanel />
      </Wrapper>
    )
    await waitFor(() => {
      expect(container.querySelector("[aria-live]")).toBeInTheDocument()
    })
  })
})
