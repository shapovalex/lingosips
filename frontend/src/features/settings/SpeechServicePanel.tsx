/**
 * SpeechServicePanel — inline Azure Speech configuration panel.
 *
 * State machine mirrors AIServicePanel.
 * AC1–AC4 (speech equivalent)
 */

import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { del, get, post } from "@/lib/client"

type SpeechServicePanelState =
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

const AZURE_REGIONS = [
  "eastus",
  "eastus2",
  "westus",
  "westus2",
  "westeurope",
  "northeurope",
  "southeastasia",
  "australiaeast",
  "japaneast",
  "uksouth",
] as const

export function SpeechServicePanel() {
  const queryClient = useQueryClient()

  const { data: serviceStatus } = useQuery<ServiceStatusResponse>({
    queryKey: ["services", "status"],
    queryFn: () => get<ServiceStatusResponse>("/services/status"),
  })

  const isConfigured = serviceStatus?.speech?.provider === "azure"
  const [panelState, setPanelState] = useState<SpeechServicePanelState>("closed")
  const [azureKey, setAzureKey] = useState("")
  const [azureRegion, setAzureRegion] = useState("eastus")
  const [testResult, setTestResult] = useState<ConnectionTestResponse | null>(null)
  const [statusMessage, setStatusMessage] = useState("")

  const currentState: SpeechServicePanelState =
    panelState === "closed" && isConfigured ? "configured" : panelState

  async function handleTest() {
    setPanelState("testing")
    setStatusMessage("Testing Azure Speech connection…")
    try {
      const result = await post<ConnectionTestResponse>("/services/test-connection", {
        provider: "azure",
        azure_key: azureKey,
        azure_region: azureRegion,
      })
      setTestResult(result)
      if (result.success) {
        setPanelState("test-success")
        setStatusMessage("Azure Speech connected")
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
    try {
      await post("/services/credentials", {
        azure_speech_key: azureKey,
        azure_speech_region: azureRegion,
      })
      await queryClient.invalidateQueries({ queryKey: ["services", "status"] })
      setPanelState("configured")
      setStatusMessage("Azure Speech credentials saved")
      setAzureKey("")
    } catch {
      setPanelState("test-success")
      setStatusMessage("Save failed — try again")
    }
  }

  async function handleRemove() {
    try {
      await del("/services/credentials/azure")
      await queryClient.invalidateQueries({ queryKey: ["services", "status"] })
      setPanelState("closed")
      setStatusMessage("Azure Speech credentials removed")
    } catch {
      setStatusMessage("Remove failed — try again")
    }
  }

  const canTest = azureKey.length > 0 && azureRegion !== ""

  return (
    <div className="rounded-lg border border-zinc-800 p-4">
      <div aria-live="polite" aria-atomic="true" className="sr-only">
        {statusMessage}
      </div>

      {(currentState === "configured" || panelState === "saving") && (
        <div className="flex items-center justify-between">
          <div>
            <span className="text-sm font-medium text-zinc-200">Azure Speech</span>
            <span className="ml-2 inline-flex h-2 w-2 rounded-full bg-green-500" />
            <span className="ml-1 text-xs text-zinc-500">active</span>
          </div>
          <button
            type="button"
            className="text-xs text-zinc-400 hover:text-zinc-200"
            onClick={handleRemove}
          >
            Remove
          </button>
        </div>
      )}

      {currentState === "closed" && !isConfigured && (
        <div className="flex items-center justify-between">
          <div>
            <span className="text-sm font-medium text-zinc-200">Local TTS</span>
            <span className="ml-1 text-xs text-zinc-500">— active</span>
          </div>
          <button
            type="button"
            className="rounded bg-zinc-700 px-3 py-1 text-xs font-medium text-zinc-100 hover:bg-zinc-600"
            onClick={() => {
              setPanelState("open-form")
              setStatusMessage("")
              setTestResult(null)
            }}
          >
            Upgrade
          </button>
        </div>
      )}

      {(currentState === "open-form" ||
        currentState === "testing" ||
        currentState === "test-success" ||
        currentState === "test-error") && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-zinc-200">Azure Speech setup</span>
            <button
              type="button"
              className="text-xs text-zinc-500 hover:text-zinc-300"
              onClick={() => {
                setPanelState("closed")
                setAzureKey("")
                setTestResult(null)
              }}
            >
              Cancel
            </button>
          </div>

          <div>
            <label
              htmlFor="azure-speech-key"
              className="block text-xs font-medium text-zinc-400 mb-1"
            >
              Azure Speech key
            </label>
            <input
              id="azure-speech-key"
              type="password"
              aria-label="Azure Speech key"
              value={azureKey}
              onChange={(e) => setAzureKey(e.target.value)}
              placeholder="your-key…"
              className="w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-zinc-500 focus:outline-none"
            />
          </div>

          <div>
            <label
              htmlFor="azure-region"
              className="block text-xs font-medium text-zinc-400 mb-1"
            >
              Region
            </label>
            <select
              id="azure-region"
              value={azureRegion}
              onChange={(e) => setAzureRegion(e.target.value)}
              className="w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 focus:border-zinc-500 focus:outline-none"
            >
              {AZURE_REGIONS.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </div>

          {currentState === "test-success" && (
            <div className="rounded bg-green-900/30 border border-green-800 px-3 py-2 text-sm text-green-300">
              ✓ Azure Speech connected
            </div>
          )}
          {currentState === "test-error" && testResult && (
            <div className="rounded bg-red-900/30 border border-red-800 px-3 py-2 text-sm text-red-300">
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
