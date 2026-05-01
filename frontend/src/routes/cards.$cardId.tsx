import { createFileRoute } from "@tanstack/react-router"
import { CardDetail } from "../features/cards"

export const Route = createFileRoute("/cards/$cardId")({
  component: CardDetailPage,
})

function CardDetailPage() {
  const { cardId } = Route.useParams()
  return (
    <div className="min-h-full p-4 md:p-8">
      <CardDetail cardId={Number(cardId)} />
    </div>
  )
}
