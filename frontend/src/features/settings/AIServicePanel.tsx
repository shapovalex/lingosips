/**
 * AIServicePanel — inline OpenRouter configuration panel.
 *
 * State machine (NEVER boolean flags — project rule):
 *   closed        → collapsed: show status + Upgrade button
 *   open-form     → form visible: api_key + model selector
 *   testing       → POST /services/test-connection in flight
 *   test-success  → sample_translation shown, Save active
 *   test-error    → specific error shown, retry available
 *   saving        → POST /services/credentials in flight
 *   configured    → provider active: show name + Remove button
 *
 * AC1, AC2, AC3, AC4
 */

import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { del, get, post } from "@/lib/client"

type AIServicePanelState =
  | "closed"
  | "open-form"
  | "testing"
  | "test-success"
  | "test-error"
  | "saving"
  | "configured"

interface ServiceStatusResponse {
  llm: { provider: string; model: string | null }
  speech: { provider: string }
}

interface ConnectionTestResponse {
  success: boolean
  sample_translation: string | null
  error_code: string | null
  error_message: string | null
}

// Hardcoded popular models — no backend endpoint needed
const POPULAR_OPENROUTER_MODELS = [
  { id: "openai/gpt-4o-mini", name: "GPT-4o Mini (Recommended)" },
  { id: "openai/gpt-4o", name: "GPT-4o" },
  { id: "anthropic/claude-3-5-haiku", name: "Claude 3.5 Haiku" },
  { id: "anthropic/claude-3-5-sonnet", name: "Claude 3.5 Sonnet" },
  { id: "google/gemini-flash-1.5", name: "Gemini Flash 1.5" },
  { id: "meta-llama/llama-3.1-8b-instruct:free", name: "Llama 3.1 8B (Free)" },
] as const

export function AIServicePanel() {
  const queryClient = useQueryClient()

  const { data: serviceStatus } = useQuery<ServiceStatusResponse>({
    queryKey: ["services", "status"],
    queryFn: () => get<ServiceStatusResponse>("/services/status"),
  })

  // Determine initial state from service status
  const isConfigured = serviceStatus?.llm?.provider === "openrouter"
  const initialState: AIServicePanelState = isConfigured ? "configured" : "closed"

  const [panelState, setPanelState] = useState<AIServicePanelState>(initialState)
  const [apiKey, setApiKey] = useState("")
  const [selectedModel, setSelectedModel] = useState("openai/gpt-4o-mini")
  const [testResult, setTestResult] = useState<ConnectionTestResponse | null>(null)
  const [statusMessage, setStatusMessage] = useState("")

  // Sync state when service status loads
  const currentState: AIServicePanelState =
    panelState === "closed" && isConfigured ? "configured" : panelState

  async function handleTest() {
    setPanelState("testing")
    setStatusMessage("Testing connection…")
    try {
      const result = await post<ConnectionTestResponse>("/services/test-connection", {
        provider: "openrouter",
        api_key: apiKey,
        model: selectedModel,
      })
      setTestResult(result)
      if (result.success) {
        setPanelState("test-success")
        setStatusMessage(`Connection successful — "${result.sample_translation}"`)
      } else {
        setPanelState("test-error")
        setStatusMessage(result.error_message ?? "Connection failed")
      }
    } catch {
      setPanelState("test-error")
      setStatusMessage("Connection failed — check your network")
    }
  }

  async function handleSave() {
    setPanelState("saving")
    setStatusMessage("Saving credentials…")
    try {
      await post("/services/credentials", {
        openrouter_api_key: apiKey,
        openrouter_model: selectedModel,
      })
      await queryClient.invalidateQueries({ queryKey: ["services", "status"] })
      setPanelState("configured")
      setStatusMessage("OpenRouter credentials saved")
      setApiKey("")
    } catch {
      setPanelState("test-success")
      setStatusMessage("Save failed — try again")
    }
  }

  async function handleRemove() {
    try {
      await del("/services/credentials/openrouter")
      await queryClient.invalidateQueries({ queryKey: ["services", "status"] })
      setPanelState("closed")
      setStatusMessage("OpenRouter credentials removed")
    } catch {
      setStatusMessage("Remove failed — try again")
    }
  }

  function handleUpgrade() {
    setPanelState("open-form")
    setStatusMessage("")
    setTestResult(null)
  }

  function handleCancel() {
    setPanelState("closed")
    setApiKey("")
    setTestResult(null)
    setStatusMessage("")
  }

  const canTest = apiKey.length > 0 && selectedModel !== ""
  const llmModel = serviceStatus?.llm?.model

  return (
    <div data-testid="ai-service-panel" className="rounded-lg border border-zinc-800 p-4">
      {/* aria-live region for state change announcements */}
      <div aria-live="polite" aria-atomic="true" className="sr-only">
        {statusMessage}
      </div>

      {/* Configured state */}
      {(currentState === "configured" || panelState === "saving") && (
        <div className="flex items-center justify-between">
          <div>
            <span className="text-sm font-medium text-zinc-200">OpenRouter</span>
            {llmModel && (
              <span className="ml-1 text-sm text-zinc-400">· {llmModel}</span>
            )}
            <span className="ml-2 inline-flex h-2 w-2 rounded-full bg-green-500" />
            <span className="ml-1 text-xs text-zinc-500">active</span>
          </div>
          <button
            type="button"
            className="text-xs text-zinc-400 hover:text-zinc-200"
            onClick={handleRemove}
            aria-label="Remove OpenRouter credentials"
          >
            Remove
          </button>
        </div>
      )}

      {/* Closed / default state */}
      {currentState === "closed" && !isConfigured && (
        <div className="flex items-center justify-between">
          <div>
            <span className="text-sm font-medium text-zinc-200">Local Qwen</span>
            <span className="ml-1 text-xs text-zinc-500">— active</span>
          </div>
          <button
            type="button"
            className="rounded bg-zinc-700 px-3 py-1 text-xs font-medium text-zinc-100 hover:bg-zinc-600"
            onClick={handleUpgrade}
          >
            Upgrade
          </button>
        </div>
      )}

      {/* Open form / testing / test-success / test-error states */}
      {(currentState === "open-form" ||
        currentState === "testing" ||
        currentState === "test-success" ||
        currentState === "test-error") && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-zinc-200">OpenRouter setup</span>
            <button
              type="button"
              className="text-xs text-zinc-500 hover:text-zinc-300"
              onClick={handleCancel}
            >
              Cancel
            </button>
          </div>

          <div>
            <p className="text-xs text-zinc-500 mb-2">
              {"Don't have an account? "}
              <a
                href="https://openrouter.ai/keys"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-400 hover:text-blue-300 underline"
                aria-label="Sign up for OpenRouter (opens in new tab)"
              >
                Sign up for OpenRouter
              </a>
            </p>
          </div>

          <div>
            <label
              htmlFor="openrouter-api-key"
              className="block text-xs font-medium text-zinc-400 mb-1"
            >
              OpenRouter API key
            </label>
            <input
              id="openrouter-api-key"
              type="password"
              aria-label="OpenRouter API key"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="sk-or-…"
              className="w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-zinc-500 focus:outline-none"
            />
          </div>

          <div>
            <label
              htmlFor="openrouter-model"
              className="block text-xs font-medium text-zinc-400 mb-1"
            >
              Model
            </label>
            <select
              id="openrouter-model"
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 focus:border-zinc-500 focus:outline-none"
            >
              {POPULAR_OPENROUTER_MODELS.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
          </div>

          {/* Test result feedback */}
          {currentState === "test-success" && testResult !== null && (
            <div
              className="rounded bg-green-900/30 border border-green-800 px-3 py-2 text-sm text-green-300"
              data-testid="test-success-message"
            >
              {testResult.sample_translation
                ? `✓ Connection OK — ${testResult.sample_translation}`
                : "✓ Connection successful"}
            </div>
          )}
          {currentState === "test-error" && testResult !== null && (
            <div
              className="rounded bg-red-900/30 border border-red-800 px-3 py-2 text-sm text-red-300"
              data-testid="test-error-message"
            >
              {testResult.error_message ?? "Connection failed"}
            </div>
          )}

          <div className="flex gap-2 pt-1">
            <button
              type="button"
              disabled={!canTest || currentState === "testing"}
              onClick={handleTest}
              className="flex-1 rounded bg-zinc-700 px-3 py-2 text-xs font-medium text-zinc-100 hover:bg-zinc-600 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {currentState === "testing" ? "Testing…" : "Test connection"}
            </button>
            {currentState === "test-success" && (
              <button
                type="button"
                onClick={handleSave}
                className="flex-1 rounded bg-blue-600 px-3 py-2 text-xs font-medium text-white hover:bg-blue-500"
              >
                Save
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
