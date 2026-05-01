import { createFileRoute } from "@tanstack/react-router"
import { CardCreationPanel } from "../features/cards"

export const Route = createFileRoute("/")({
  component: HomePage,
})

function HomePage() {
  return (
    <div className="flex min-h-full p-4 md:p-8">
      <div className="w-full max-w-2xl">
        <CardCreationPanel />
      </div>
    </div>
  )
}
