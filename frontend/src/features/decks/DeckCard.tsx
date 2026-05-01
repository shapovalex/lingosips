/**
 * DeckCard — individual deck card with inline rename and delete confirmation.
 *
 * State machine: viewing | renaming | confirm-delete | deleting
 */

import { useRef, useState } from "react"
import { Link } from "@tanstack/react-router"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

export type DeckCardState = "viewing" | "renaming" | "confirm-delete" | "deleting"

export interface DeckResponse {
  id: number
  name: string
  target_language: string
  card_count: number
  due_card_count: number
  created_at: string
  updated_at: string
}

interface DeckCardProps {
  deck: DeckResponse
  onRename: (newName: string) => void
  onDelete: () => void
}

export function DeckCard({ deck, onRename, onDelete }: DeckCardProps) {
  const [state, setState] = useState<DeckCardState>("viewing")
  const [draft, setDraft] = useState(deck.name)
  // Tracks whether the rename was already settled by a keypress (Enter/Escape).
  // Prevents the unmount-triggered blur from firing a duplicate or spurious rename.
  const renameSettledRef = useRef(false)

  function handleRenameButtonClick(e: React.MouseEvent) {
    e.stopPropagation()
    e.preventDefault()
    setDraft(deck.name)
    renameSettledRef.current = false // reset whenever entering rename mode
    setState("renaming")
  }

  function handleDeleteButtonClick(e: React.MouseEvent) {
    e.stopPropagation()
    e.preventDefault()
    setState("confirm-delete")
  }

  function handleRenameKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      renameSettledRef.current = true // mark settled BEFORE setState to guard the blur
      if (draft.trim()) {
        onRename(draft.trim())
      }
      setState("viewing")
    } else if (e.key === "Escape") {
      renameSettledRef.current = true // mark settled (cancelled) — blur must not save
      setState("viewing")
    }
  }

  function handleRenameBlur() {
    if (renameSettledRef.current) {
      // Already handled by Enter or Escape — this blur is the unmount echo; ignore it.
      return
    }
    // Genuine focus-loss (user clicked away): save only if the name actually changed.
    if (draft.trim() && draft.trim() !== deck.name) {
      onRename(draft.trim())
    }
    setState("viewing")
  }

  function handleConfirmDelete() {
    setState("deleting")
    onDelete()
  }

  return (
    <>
      <Card className="hover:border-zinc-700 transition-colors relative group">
        {state === "renaming" ? (
          <div className="p-4">
            <input
              autoFocus
              className="w-full bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-zinc-50 text-base focus:outline-none focus:ring-1 focus:ring-indigo-500"
              value={draft}
              aria-label={`Rename ${deck.name}`}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={handleRenameKeyDown}
              onBlur={handleRenameBlur}
              onClick={(e) => e.stopPropagation()}
            />
            <div className="flex gap-2 mt-2 flex-wrap">
              <Badge variant="secondary">{deck.target_language.toUpperCase()}</Badge>
            </div>
          </div>
        ) : (
          <Link
            to="/decks/$deckId"
            params={{ deckId: String(deck.id) }}
            className="block p-4 focus:outline-none focus:ring-1 focus:ring-indigo-500 rounded-lg"
          >
            <p className="font-semibold text-zinc-50">{deck.name}</p>
            <div className="flex gap-2 mt-2 flex-wrap">
              <Badge variant="secondary">{deck.target_language.toUpperCase()}</Badge>
              <Badge variant="outline">{deck.card_count} cards</Badge>
              {deck.due_card_count > 0 && (
                <Badge
                  variant="outline"
                  className="text-amber-500 border-amber-500"
                  aria-label={`${deck.due_card_count} cards due for review`}
                >
                  {deck.due_card_count} due
                </Badge>
              )}
            </div>
          </Link>
        )}

        {/* Action buttons — visible on group-hover / focus-within */}
        <div className="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity">
          <Button
            variant="ghost"
            size="icon"
            aria-label={`Rename ${deck.name}`}
            onClick={handleRenameButtonClick}
          >
            ✏️
          </Button>
          <Button
            variant="ghost"
            size="icon"
            aria-label={`Delete ${deck.name}`}
            onClick={handleDeleteButtonClick}
          >
            🗑️
          </Button>
        </div>
      </Card>

      {/* Delete confirmation dialog */}
      <Dialog
        open={state === "confirm-delete" || state === "deleting"}
        onOpenChange={(open) => !open && setState("viewing")}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete deck · This cannot be undone</DialogTitle>
            <DialogDescription className="sr-only">
              Cards in this deck will remain in your collection.
            </DialogDescription>
          </DialogHeader>
          <p className="text-sm text-zinc-400">
            Cards assigned to this deck will remain in your collection without a deck.
          </p>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setState("viewing")}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleConfirmDelete}
              disabled={state === "deleting"}
            >
              {state === "deleting" ? "Deleting..." : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
