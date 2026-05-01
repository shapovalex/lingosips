import { createFileRoute } from "@tanstack/react-router"

export const Route = createFileRoute("/decks/$deckId")({
  component: DeckDetailPage,
})

function DeckDetailPage() {
  // Stub: full card-in-deck listing is a future story
  return (
    <div className="p-4 md:p-8">
      <p className="text-zinc-400 text-sm">Deck detail — coming in a future story.</p>
    </div>
  )
}
