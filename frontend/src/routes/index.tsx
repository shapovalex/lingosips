import { createFileRoute } from "@tanstack/react-router"

export const Route = createFileRoute("/")({
  component: HomePage,
})

function HomePage() {
  return (
    <div className="flex min-h-full items-center justify-center p-8">
      <div className="max-w-md text-center">
        <h1 className="text-3xl font-bold text-zinc-50">Welcome to lingosips</h1>
        <p className="mt-4 text-zinc-400">
          Your local-first vocabulary learning app with spaced repetition.
        </p>
        <p className="mt-2 text-sm text-zinc-400">
          Get started by creating your first deck.
        </p>
      </div>
    </div>
  )
}
