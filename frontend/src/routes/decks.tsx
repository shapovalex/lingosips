import { createFileRoute } from "@tanstack/react-router"
import { DeckGrid } from "../features/decks"

export const Route = createFileRoute("/decks")({
  component: DecksPage,
})

function DecksPage() {
  return <DeckGrid />
}
