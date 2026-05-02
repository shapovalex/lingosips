import { createFileRoute, Outlet } from "@tanstack/react-router"

export const Route = createFileRoute("/decks")({
  component: DecksLayout,
})

/**
 * Layout route for /decks and /decks/$deckId.
 * Renders <Outlet /> so child routes (DeckGrid index, DeckDetail) can appear.
 */
function DecksLayout() {
  return <Outlet />
}
