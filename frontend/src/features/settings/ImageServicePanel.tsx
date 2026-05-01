/**
 * ImageServicePanel — inline image endpoint configuration panel.
 *
 * State machine mirrors AIServicePanel.
 * MVP: always starts in "closed" state (no persistence check for image status).
 */

import { useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { del, post } from "@/lib/client"

type ImageServicePanelState =
  | "closed"
  | "open-form"
  | "testing"
  | "test-success"
  | "test-error"
  | "saving"
  | "configured"

interface ConnectionTestResponse {
  success: boolean
  sample_translation: string | null
  error_code: string | null
  error_message: string | null
}

export function ImageServicePanel() {
  const queryClient = useQueryClient()

  const [panelState, setPanelState] = useState<ImageServicePanelState>("closed")
  const [endpointUrl, setEndpointUrl] = useState("")
  const [endpointKey, setEndpointKey] = useState("")
  const [testResult, setTestResult] = useState<ConnectionTestResponse | null>(null)
  const [statusMessage, setStatusMessage] = useState("")

  async function handleTest() {
    setPanelState("testing")
    setStatusMessage("Testing image endpoint…")
    try {
      const result = await post<ConnectionTestResponse>("/services/test-connection", {
        provider: "image",
        endpoint_url: endpointUrl,
        endpoint_key: endpointKey || undefined,
      })
      setTestResult(result)
      if (result.success) {
        setPanelState("test-success")
        setStatusMessage("Image endpoint reachable")
      } else {
        setPanelState("test-error")
        setStatusMessage(result.error_message ?? "Connection failed")
      }
    } catch {
      setPanelState("test-error")
      setStatusMessage("Connection failed — check the URL")
    }
  }

  async function handleSave() {
    setPanelState("saving")
    try {
      await post("/services/credentials", {
        image_endpoint_url: endpointUrl,
        ...(endpointKey ? { image_endpoint_key: endpointKey } : {}),
      })
      await queryClient.invalidateQueries({ queryKey: ["services", "status"] })
      setPanelState("configured")
      setStatusMessage("Image endpoint saved")
      setEndpointUrl("")
      setEndpointKey("")
    } catch {
      setPanelState("test-success")
      setStatusMessage("Save failed — try again")
    }
  }

  async function handleRemove() {
    try {
      await del("/services/credentials/image")
      await queryClient.invalidateQueries({ queryKey: ["services", "status"] })
      setPanelState("closed")
      setStatusMessage("Image endpoint credentials removed")
    } catch {
      setStatusMessage("Remove failed — try again")
    }
  }

  const canTest = endpointUrl.length > 0

  return (
    <div className="rounded-lg border border-zinc-800 p-4">
      <div aria-live="polite" aria-atomic="true" className="sr-only">
        {statusMessage}
      </div>

      {panelState === "configured" && (
        <div className="flex items-center justify-between">
          <div>
            <span className="text-sm font-medium text-zinc-200">Image endpoint</span>
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

      {panelState === "closed" && (
        <div className="flex items-center justify-between">
          <div>
            <span className="text-sm font-medium text-zinc-200">Image generation</span>
            <span className="ml-1 text-xs text-zinc-500">— not configured</span>
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
            Configure
          </button>
        </div>
      )}

      {(panelState === "open-form" ||
        panelState === "testing" ||
        panelState === "test-success" ||
        panelState === "test-error") && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-zinc-200">Image endpoint setup</span>
            <button
              type="button"
              className="text-xs text-zinc-500 hover:text-zinc-300"
              onClick={() => {
                setPanelState("closed")
                setEndpointUrl("")
                setEndpointKey("")
                setTestResult(null)
              }}
            >
              Cancel
            </button>
          </div>

          <div>
            <label
              htmlFor="image-endpoint-url"
              className="block text-xs font-medium text-zinc-400 mb-1"
            >
              Endpoint URL
            </label>
            <input
              id="image-endpoint-url"
              type="url"
              aria-label="Image endpoint URL"
              value={endpointUrl}
              onChange={(e) => setEndpointUrl(e.target.value)}
              placeholder="https://your-image-api.example.com"
              className="w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-zinc-500 focus:outline-none"
            />
          </div>

          <div>
            <label
              htmlFor="image-endpoint-key"
              className="block text-xs font-medium text-zinc-400 mb-1"
            >
              API key{" "}
              <span className="font-normal text-zinc-600">(optional)</span>
            </label>
            <input
              id="image-endpoint-key"
              type="password"
              aria-label="Image endpoint API key"
              value={endpointKey}
              onChange={(e) => setEndpointKey(e.target.value)}
              placeholder="optional key…"
              className="w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-zinc-500 focus:outline-none"
            />
          </div>

          {panelState === "test-success" && (
            <div className="rounded bg-green-900/30 border border-green-800 px-3 py-2 text-sm text-green-300">
              ✓ Image endpoint reachable
            </div>
          )}
          {panelState === "test-error" && testResult && (
            <div className="rounded bg-red-900/30 border border-red-800 px-3 py-2 text-sm text-red-300">
              {testResult.error_message ?? "Connection failed"}
            </div>
          )}

          <div className="flex gap-2 pt-1">
            <button
              type="button"
              disabled={!canTest || panelState === "testing"}
              onClick={handleTest}
              className="flex-1 rounded bg-zinc-700 px-3 py-2 text-xs font-medium text-zinc-100 hover:bg-zinc-600 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {panelState === "testing" ? "Testing…" : "Test connection"}
            </button>
            {panelState === "test-success" && (
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
