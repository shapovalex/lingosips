import { createFileRoute } from "@tanstack/react-router"
import { ServiceStatusIndicator } from "@/components/ServiceStatusIndicator"
import {
  AIServicePanel,
  SpeechServicePanel,
  ImageServicePanel,
  LanguageSection,
  SystemDefaultsSection,
} from "@/features/settings"

export const Route = createFileRoute("/settings")({
  component: SettingsPage,
})

function SettingsPage() {
  return (
    <div className="p-6 md:p-8 max-w-2xl">
      {/* ServiceStatusIndicator in header — mobile only (md+ uses sidebar footer) */}
      <div className="md:hidden mb-6 pb-4 border-b border-zinc-800">
        <ServiceStatusIndicator />
      </div>
      <h1 className="text-2xl font-semibold text-zinc-50 mb-8">Settings</h1>

      <section aria-labelledby="ai-services-heading" className="mb-10">
        <h2
          id="ai-services-heading"
          className="text-lg font-medium text-zinc-300 mb-4"
        >
          AI Services
        </h2>
        <div className="space-y-3">
          <AIServicePanel />
          <SpeechServicePanel />
          <ImageServicePanel />
        </div>
      </section>

      <section aria-labelledby="languages-heading" className="mb-10">
        <h2
          id="languages-heading"
          className="text-lg font-medium text-zinc-300 mb-4"
        >
          Languages
        </h2>
        <LanguageSection />
      </section>

      <section aria-labelledby="defaults-heading" className="mb-10">
        <h2
          id="defaults-heading"
          className="text-lg font-medium text-zinc-300 mb-4"
        >
          Study Defaults
        </h2>
        <SystemDefaultsSection />
      </section>
    </div>
  )
}
