/**
 * SSE consumer for GET /import/{job_id}/progress.
 *
 * IMPORTANT: this is a GET SSE stream — NOT streamPost (which is for POST /cards/stream).
 * Use native EventSource API (browser-native, no polyfill needed for modern browsers).
 */

import { useEffect, useRef } from "react"
import { useAppStore, type ImportProgress } from "@/lib/stores/useAppStore"

export type { ImportProgress }

export function useImportProgress(jobId: number | null): ImportProgress {
  const setImportProgress = useAppStore((s) => s.setImportProgress)
  const importProgress = useAppStore((s) => s.importProgress)
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    if (!jobId) return

    // Close any existing connection
    esRef.current?.close()

    const es = new EventSource(`/import/${jobId}/progress`)
    esRef.current = es

    es.addEventListener("progress", (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data)
        setImportProgress({
          done: data.done,
          total: data.total,
          currentItem: data.current_item ?? null,
          status: "running",
          enriched: 0,
          unresolved: 0,
          errorMessage: null,
        })
      } catch {
        // Malformed event — ignore
      }
    })

    es.addEventListener("complete", (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data)
        setImportProgress({
          done: data.enriched + data.unresolved,
          total: data.enriched + data.unresolved,
          currentItem: null,
          status: "complete",
          enriched: data.enriched,
          unresolved: data.unresolved,
          errorMessage: null,
        })
        // Fire completion notification — omit unresolved clause when zero (AC7)
        const msg =
          data.unresolved > 0
            ? `${data.enriched} cards enriched · ${data.unresolved} fields could not be resolved`
            : `${data.enriched} cards enriched`
        useAppStore.getState().addNotification({
          type: "success",
          message: msg,
        })
        useAppStore.getState().setActiveImportJobId(null)
        es.close()
        esRef.current = null
      } catch {
        // Malformed event — ignore
      }
    })

    es.addEventListener("error", (e: Event) => {
      // SSE 'error' event can mean connection dropped OR our custom error event
      const errorEvent = e as MessageEvent
      if (errorEvent.data) {
        try {
          const data = JSON.parse(errorEvent.data)
          setImportProgress({
            ...useAppStore.getState().importProgress,
            status: "error",
            errorMessage: data.message ?? "Import failed",
          })
        } catch {
          // Malformed error event
        }
      }
      es.close()
      esRef.current = null
    })

    return () => {
      es.close()
      esRef.current = null
    }
  }, [jobId]) // eslint-disable-line react-hooks/exhaustive-deps

  return importProgress
}
