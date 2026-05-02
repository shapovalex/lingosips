import { createFileRoute } from "@tanstack/react-router"
import { useQuery } from "@tanstack/react-query"
import { get } from "@/lib/client"
import { DeckExportImport } from "@/features/decks"
import type { DeckResponse } from "@/features/decks"
import { Skeleton } from "@/components/ui/skeleton"
import { Badge } from "@/components/ui/badge"

export const Route = createFileRoute("/decks/$deckId")({
  component: DeckDetailPage,
})

function DeckDetailPage() {
  const { deckId } = Route.useParams()
  const id = Number(deckId)

  const {
    data: deck,
    isLoading,
    isError,
  } = useQuery<DeckResponse>({
    queryKey: ["decks", id],
    queryFn: () => get<DeckResponse>(`/decks/${id}`),
  })

  if (isLoading) {
    return (
      <div className="p-4 md:p-8 space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-10 w-40" />
      </div>
    )
  }

  if (isError || !deck) {
    return (
      <div className="p-4 md:p-8">
        <p className="text-red-400">Deck not found</p>
      </div>
    )
  }

  return (
    <div className="p-4 md:p-8 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3 flex-wrap">
        <h1 className="text-2xl font-semibold text-zinc-50">{deck.name}</h1>
        <Badge variant="secondary">{deck.target_language.toUpperCase()}</Badge>
        <span className="text-zinc-400 text-sm">
          {deck.card_count} cards · {deck.due_card_count} due
        </span>
      </div>

      {/* Export / Import controls */}
      <DeckExportImport deckId={deck.id} deckName={deck.name} />

      {/* Card browsing stub */}
      <p className="text-zinc-400 text-sm">Card browsing — coming in a future story.</p>
    </div>
  )
}
