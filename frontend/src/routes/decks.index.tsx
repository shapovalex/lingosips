import { createFileRoute } from "@tanstack/react-router"
import { DeckGrid } from "../features/decks"

export const Route = createFileRoute("/decks/")({
  component: DecksIndexPage,
})

function DecksIndexPage() {
  return <DeckGrid />
}
