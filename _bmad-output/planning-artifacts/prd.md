---
stepsCompleted: ["step-01-init", "step-02-discovery", "step-02b-vision", "step-02c-executive-summary", "step-03-success", "step-04-journeys", "step-05-domain", "step-06-innovation", "step-07-project-type", "step-08-scoping", "step-09-functional", "step-10-nonfunctional", "step-11-polish"]
releaseMode: phased
inputDocuments: []
workflowType: 'prd'
classification:
  projectType: web_app
  domain: edtech
  complexity: medium
  projectContext: greenfield
---

# Product Requirements Document - lingosips

**Author:** Oleksii
**Date:** 2026-04-26

## Executive Summary

Lingosips is a local-first, open-source language learning application. Cloud AI services (OpenRouter, Azure Speech) deliver the primary experience; local models (Qwen, Whisper) activate as fallback when cloud services are not configured, ensuring the app works without any keys. It targets self-directed language learners frustrated by existing tools: Anki's inability to generate pronunciation audio or support speaking practice, Duolingo's shallow vocabulary and lack of user control, and the universal cold-start friction of building a deck from scratch. Lingosips eliminates that friction — type a word or phrase, AI fills translation, audio, example sentences, context, and optionally an image — while providing a full practice loop (self-assess, write, speak) with real AI feedback at every step.

### What Makes This Special

- **Cloud-first with local fallback:** OpenRouter (LLM) and Azure Speech are the primary services. Local Qwen and Whisper activate automatically when cloud services are not configured — zero keys required to start, full quality when configured.
- **FSRS-powered spaced repetition:** Scientifically optimized scheduling manages review intervals automatically, surfacing the right cards at the right time.
- **Full practice modality coverage:** Self-assess (classic flip), write (typed answer with AI feedback), and speak (pronunciation verification via Azure Speech or local Whisper) — three modes supporting different learning styles.
- **Sentence and collocation focus:** Practice moves beyond isolated vocabulary to sentence-level and collocation translation — the most linguistically differentiated feature in the product.
- **Inline AI assistance everywhere:** From card creation to practice, AI catches mistakes, suggests fixes, and provides feedback — embedded tutor, not a bolt-on feature.
- **CEFR learner intelligence:** System builds a continuous knowledge profile and explains exactly where the user sits on the A1–C2 scale, what they demonstrate confidently, and what gaps separate them from the next level.
- **OpenRouter gateway:** One API key unlocks hundreds of LLM models. Azure Speech and image generation endpoints supported with in-app guided setup.

## Project Classification

- **Project Type:** Web App (SPA, local-first, installable via Electron or similar; also runs as web application)
- **Domain:** EdTech — personal language learning
- **Complexity:** Medium (AI/speech integration adds technical depth; no compliance burden — single-user, no-auth, no-multi-tenancy)
- **Project Context:** Greenfield
- **Deployment:** Open-source; local desktop app primary; web app secondary; single user; no authentication; no multi-tenancy

## Success Criteria

### User Success

- User creates a complete, linguistically accurate card (translation, gender/article, plural, conjugation, pronunciation audio, example sentences) by entering a single word or phrase — no manual correction required
- User completes a practice session in at least one mode within the first 5 minutes of app use, with zero configuration
- User never needs an external dictionary for grammar details — the card is authoritative
- Pronunciation feedback identifies the specific error (syllable-level) — not just "wrong/right"
- FSRS scheduling surfaces the right cards at the right time — user notices vocabulary retention across sessions

### Business Success

- Open-source community adoption: stars, forks, contributions over time
- Self-sustaining daily use: users return without external reminders (retention earned, not gamified)

### Technical Success

- Card creation pipeline completes in < 3 seconds (OpenRouter); < 5 seconds (local Qwen fallback)
- Speech evaluation latency < 2 seconds (Azure Speech or local Whisper)
- App runs fully offline — all core features functional without network except image generation and cloud-key features
- OpenRouter integration works with any configured model — no model-specific hardcoding

### Measurable Outcomes

- Time from app launch to first completed card: < 60 seconds
- Card quality: user edits fewer than 5% of AI-generated fields
- Zero required configuration to reach first practice session

## User Journeys

### Journey 1: The Self-Directed Learner — First Session (Happy Path)

**Persona:** Oleksii, 34, software engineer learning Spanish. Has tried Anki twice — abandoned both times because building cards felt like homework before the actual studying.

**Opening Scene:** He downloads lingosips on a Tuesday evening. No account creation screen. The app opens directly to a clean card creation interface. A language selector asks for native language (Ukrainian) and target language (Spanish). Done in 10 seconds.

**Rising Action:** He types "melancólico." In under 3 seconds: translation appears, gender (masculino/femenino), plural (melancólicos/melancólicas), an example sentence, pronunciation audio. He hits play — the audio sounds natural. He didn't ask for any of that. It just happened. He creates 8 more cards in 4 minutes. He hasn't opened a dictionary once.

**Climax:** He clicks "Practice." FSRS shows him the 3 cards most due. He picks Write mode. Types his answer. Gets it slightly wrong — the app highlights the error, shows the correct form, explains *why* (adjective agreement). Not a red mark — a tutor's note.

**Resolution:** 15 minutes after opening the app for the first time, he has a deck and a completed practice session. He closes the app thinking "I'll do this again tomorrow." He does.

**Capabilities revealed:** Language selection on first launch, AI card creation pipeline, FSRS scheduling, Write mode with inline AI feedback.

---

### Journey 2: The Vocabulary Capture Moment (Edge Case)

**Persona:** Same Oleksii, day 12. Watching an Argentine film. A character says *"no te hagas el desentendido"* — he doesn't know it but the tone told him everything. The moment is alive. He has 90 seconds before it fades.

**Opening Scene:** He switches to lingosips (already open in background). Pastes the full phrase into the card creation field.

**Rising Action:** The AI identifies the collocation, explains the idiomatic meaning ("don't play dumb"), provides register context (informal, River Plate Spanish), generates an example sentence in context, and flags the reflexive verb construction.

**Climax:** He adds a note: "heard in film, guy confronting his brother." Card saved. Total time: 25 seconds. The moment isn't lost.

**Resolution:** Three weeks later, FSRS surfaces this card. He reads his own note. The scene comes back. He nails the translation instantly. The context was the memory hook — the app preserved it.

**Capabilities revealed:** Phrase/collocation input, idiomatic/contextual AI enrichment, user notes field on cards, FSRS long-term scheduling.

---

### Journey 3: The Returning Learner — Day 30 (Speak Mode)

**Persona:** Oleksii, day 30. 180 cards. Wants to test his pronunciation — he's been avoiding it.

**Opening Scene:** He opens the app. FSRS dashboard shows 22 cards due. He selects Speak mode for the first time.

**Rising Action:** First card: *"el aguacate."* He says it. Azure Speech processes — under 2 seconds. Feedback: stress on wrong syllable, "a-gua-CA-te not A-gua-cate." He tries again. Correct. Next card: *"no te hagas el desentendido."* Feedback is granular — first two words correct, stumbled on "desentendido," specific syllable flagged.

**Climax:** He gets 14 of 22 right on first attempt. The app schedules the 8 he missed for sooner review. 18 minutes. It felt like a conversation drill, not a test.

**Resolution:** He now defaults to Speak mode for sentence cards. His pronunciation improves visibly in his weekly italki sessions. He tells a friend about the app.

**Capabilities revealed:** Speak mode with Azure Speech, per-syllable pronunciation feedback, session summary, FSRS reschedule on failure, mixed card types in one session.

---

### Journey 4: The Importer

**Persona:** Marta, 28, learning Italian for 6 months with a manually-built Anki deck (400 cards) and a saved vocabulary list from an Italian news site she reads weekly.

**Opening Scene:** She finds lingosips via GitHub. Creates 3 cards manually — immediately notices the AI fills things her Anki cards never had (gender, conjugation tables, natural audio). She wants her 400 cards in here.

**Rising Action:** She exports her Anki deck as a text file and imports it. The app offers to AI-enrich each card (gender, audio, example sentences, missing fields). She approves; processing runs in the background. She also pastes a La Repubblica paragraph — lingosips identifies 6 unknown words, previews them, lets her confirm which to add.

**Climax:** 15 minutes later: 400 enriched cards, 6 new ones from today's article. Her entire existing investment is now inside a better tool.

**Resolution:** Marta is now a daily user. She imports every La Repubblica article she reads. Her deck grows organically from her actual reading material.

**Capabilities revealed:** Anki deck import, text/URL import, AI enrichment of imported cards, unknown word detection in pasted text, batch background processing.

---

### Journey 5: The Configurator — First-Time Key Setup

**Persona:** Dmitri, 41, wants cloud AI quality. He has an OpenRouter account and wants to use Claude for card generation.

**Opening Scene:** He opens Settings. Three sections: AI ("Local Qwen — active"), Speech ("Local Whisper — active"), Images ("Not configured"). Each has an "Upgrade" button.

**Rising Action:** He clicks "Upgrade" on AI. Guided panel: "Connect OpenRouter for access to 200+ models." Step 1: link to OpenRouter signup. Step 2: paste API key. Step 3: model selector (Claude Haiku, GPT-4o-mini, Mistral pre-filtered). He picks Claude Haiku, hits "Test connection" — a sample card generates in 2 seconds.

**Climax:** He saves. The app switches to OpenRouter seamlessly. New cards use Claude Haiku. The example sentences are noticeably more nuanced.

**Resolution:** Dmitri keeps Local Whisper for speech (latency is fine) but uses OpenRouter for card creation. He feels in control without feeling technical.

**Capabilities revealed:** Settings UI with upgrade prompts per service, OpenRouter integration with model selector, connection test, graceful fallback display, hybrid local/cloud configuration.

---

### Journey Requirements Summary

| Capability | Journeys |
|---|---|
| AI card creation pipeline (word → full card) | 1, 2, 4 |
| Phrase/collocation + idiomatic enrichment | 2 |
| User notes field on cards | 2 |
| FSRS scheduling + rescheduling on failure | 1, 3 |
| Write mode + inline AI feedback | 1 |
| Speak mode + per-syllable feedback | 3 |
| Import (Anki deck, text, URL) + AI enrichment | 4 |
| Unknown word detection in pasted text | 4 |
| Progress/session dashboard | 3 |
| Settings UI with per-service upgrade flow | 5 |
| OpenRouter integration + model selector | 5 |
| Hybrid local/cloud configuration | 5 |

## Domain-Specific Requirements

### Data Privacy

- All user data (cards, progress, settings, API keys) stored locally — no telemetry, no analytics, no external transmission except to explicitly configured services
- Explicit architectural constraint: the app never silently transmits data to any third party

### API Key Security

- All credentials (OpenRouter, Azure Speech, image endpoint) stored securely — never plaintext in config files, never in logs, never transmitted to any service other than their intended endpoint

### Content Safety

- AI-generated content (example sentences, images) passes through a content filtering layer before display
- Image generation includes a safety filter to prevent inappropriate outputs

## Innovation & Novel Patterns

### Detected Innovation Areas

**1. Cloud-first AI with guaranteed local fallback**
OpenRouter and Azure Speech deliver the primary experience. Local Qwen and Whisper guarantee the app works without any keys — no competitor in the edtech space offers this architecture. The fallback is not a degraded mode; it is a complete, working product.

**2. Zero-cognitive-overhead card creation**
The explicit design goal that the user never verifies or corrects AI output (gender, forms, conjugation, pronunciation). This raises the bar from "AI assists" to "AI is authoritative." No existing tool sets this as a success criterion.

**3. CEFR learner intelligence with explanatory profiling**
Not just a level badge — a continuous knowledge profile that explains what the learner demonstrates confidently, what gaps exist, and what specifically separates them from the next CEFR level. No current language learning tool provides this depth of self-assessment.

### Market Context & Competitive Landscape

- **Anki:** Powerful FSRS scheduling; no AI; no pronunciation support; high card creation friction
- **Duolingo:** Gamified; cloud-only; curated shallow content; no user vocabulary control
- **Babbel/Rosetta Stone:** Structured curriculum; no spaced repetition customization; cloud-only
- **Gap:** No tool combines FSRS + AI card generation + speech evaluation + CEFR profiling + BYOK cloud upgrades in a single local-capable application

### Validation Approach

- Card quality: edit rate on AI-generated fields < 5%
- Pronunciation feedback effectiveness: re-attempt success rate after speech feedback
- Zero-config onboarding: time from launch to first completed practice session < 60 seconds
- Local fallback viability: Qwen card creation latency on representative hardware < 5 seconds

### Risk Mitigation

- **Local LLM quality:** Qwen may not meet "authoritative" bar for all language pairs — define minimum thresholds per language, surface confidence indicators, drive users toward OpenRouter via onboarding
- **Whisper fallback accuracy:** Local speech evaluation may struggle with accents or low-quality microphones — clear retry UX, Azure Speech as the higher-quality primary path
- **Storage abstraction complexity:** Local-first + web app requires a deliberate storage layer from day one — decide canonical model (SQLite desktop / browser-compatible abstraction web) before writing UI

## Project Scoping & Phased Development

### MVP Strategy & Philosophy

**MVP Approach:** Experience MVP — the first release delivers a complete, polished end-to-end learning loop. Every capability that ships meets the "authoritative AI, zero cognitive overhead" standard.

**AI Service Priority Model:** Cloud-first, local-as-fallback.
- LLM: OpenRouter primary; local Qwen fallback when OpenRouter not configured
- Speech: Azure Speech primary; local Whisper fallback when Azure Speech not configured

Onboarding prominently guides users to configure OpenRouter and Azure Speech. Local models ensure the app works without any configuration — not the preferred experience.

**Resource Requirements:** Solo developer or small team (1–3). Open-source, community contributions welcome post-launch.

### MVP Feature Set (Phase 1)

**Core User Journeys Supported:** All five (first session, vocabulary capture, returning learner/speak, importer, configurator)

**Must-Have Capabilities:**
- AI card creation: word/phrase → translation, gender/article, plural, conjugation, pronunciation audio, example sentences — OpenRouter primary, local Qwen fallback
- Optional per-card image generation (requires configured image endpoint)
- Practice modes: self-assess, write (AI feedback), speak (Azure Speech primary, Whisper fallback)
- Sentence/collocation translation practice
- FSRS scheduling with automatic interval management
- Inline AI error correction during practice
- Import: Anki deck, plain text, URL — with AI enrichment of imported cards
- Progress dashboard and vocabulary size visualization
- CEFR knowledge profile with explanatory level assessment
- Deck sharing: file-based export/import (shareable deck file format)
- Multiple target languages managed simultaneously
- System-wide and deck-level configurable defaults (audio generation, image generation, practice mode, cards per session)
- Settings: native/target language(s), OpenRouter key + model, Azure Speech credentials, image generation endpoint, Whisper model
- Guided in-app onboarding for all external service keys
- Fully responsive UI (desktop primary, mobile-functional)

### Post-MVP Features (Phase 2)

- Hosted community deck repository (browse, search, install shared decks)
- Mobile companion app / PWA optimizations
- Browser extension for one-click vocabulary capture from any webpage

### Vision (Phase 3)

- Context capture (attach source — article, video, conversation — to cards for richer memory hooks)
- Collaborative / shared learning spaces

### Risk Mitigation Strategy

**Technical Risks:**
- *AI service fallback chain:* Onboarding must prominently guide users to configure OpenRouter and Azure Speech; local fallback is the safety net, not the goal
- *Storage abstraction:* Canonical storage model must be decided before writing UI — SQLite (desktop) with browser-compatible abstraction (web)
- *Scope breadth:* If velocity is lower than expected, speak mode is the first candidate to defer to Phase 2

**Market Risks:**
- *Cold-start:* Mitigated by Anki/text/URL import — users bring existing material
- *BYOK barrier:* Mitigated by functional local fallback requiring zero keys; onboarding drives toward cloud configuration

## Web App Specific Requirements

### Architecture Overview

Single-page application (SPA) with app-shell architecture. Primary deployment: local desktop app (Electron or similar) with local AI inference running as embedded or sidecar process. Secondary deployment: web app accessible from any browser including mobile, proxying AI requests to a locally-running inference server or cloud services.

### Browser & Platform Support

- Modern evergreen browsers: Chrome, Firefox, Safari, Edge (latest 2 major versions)
- No legacy browser support
- Desktop: primary design target
- Mobile browsers: full functional support required — practice sessions, card review, deck browsing comfortable on small screens; card creation may use a simplified mobile flow

### Real-Time Requirements

- AI card generation streams token-by-token — first token visible within 500ms of request
- Speech evaluation: utterance-end to feedback display < 2 seconds
- Practice session UI: optimistic updates, no blocking spinners during card transitions, 60fps animations

### Storage & Offline Architecture

- All card data, progress, settings, and credentials stored locally (SQLite for desktop; browser-compatible abstraction for web)
- App functions fully without network — network calls are additive, never required
- Writes are durable before confirmation is shown to user — no data loss on crash

## Functional Requirements

### Card Management

- **FR1:** User can create a card by entering a single word or phrase
- **FR2:** System auto-generates translation, grammatical forms (gender, article, plural, conjugation), example sentences, and pronunciation audio for a card
- **FR3:** User can add a personal note to any card
- **FR4:** User can manually edit any AI-generated field on a card
- **FR5:** User can assign a card to one or more decks
- **FR6:** User can delete a card
- **FR7:** System can generate an image for a card using a configured image generation endpoint
- **FR8:** User can trigger or skip image generation per card

### Deck Management

- **FR9:** User can create, rename, and delete decks
- **FR10:** User can browse and filter their deck collection
- **FR11:** User can export a deck to a shareable file format
- **FR12:** User can import a deck from a file
- **FR13:** User can import vocabulary from plain text, a URL, or an Anki-formatted file
- **FR14:** System detects unknown words in imported text and proposes them as new cards
- **FR15:** System AI-enriches imported cards that are missing fields (translation, grammar forms, audio, examples)
- **FR16:** User can manage multiple target languages simultaneously and switch between them

### Practice & Learning

- **FR17:** User can start a practice session for a deck or due-card queue
- **FR18:** User can practice in self-assess mode (view card, self-rate recall)
- **FR19:** User can practice in write mode (type the answer)
- **FR20:** System evaluates a written answer and highlights errors with correction suggestions
- **FR21:** User can practice in speak mode (record pronunciation of the target word or sentence)
- **FR22:** System evaluates spoken pronunciation and provides specific feedback on errors including syllable-level detail
- **FR23:** User can practice sentence and collocation translation
- **FR24:** System schedules cards using the FSRS algorithm based on user recall ratings
- **FR25:** System reschedules a card sooner when the user fails to recall it correctly

### AI & Speech Services

- **FR26:** System routes LLM requests to OpenRouter when configured, falling back to local Qwen when not configured
- **FR27:** System routes speech evaluation requests to Azure Speech when configured, falling back to local Whisper when not configured
- **FR28:** System streams AI-generated content token-by-token during card creation
- **FR29:** System tests connectivity and validity of a configured external service (OpenRouter, Azure Speech, image endpoint) on demand

### Settings & Configuration

- **FR30:** User can set their native language and one or more target languages
- **FR31:** User can configure OpenRouter API key and select a model
- **FR32:** User can configure Azure Speech credentials
- **FR33:** User can configure an image generation endpoint and credentials
- **FR34:** User can configure Whisper model selection for local speech fallback
- **FR35:** System stores all credentials securely in local storage — never plaintext
- **FR36:** User can configure system-wide default behaviors (auto-generate audio for new cards, auto-generate images, default practice mode, cards per session)
- **FR37:** User can override system-wide defaults at the deck level

### Onboarding

- **FR38:** System presents a guided onboarding flow for each external service (OpenRouter, Azure Speech, image generation) with step-by-step setup instructions
- **FR39:** System is fully functional before any external service is configured (local fallback active)
- **FR40:** User reaches a first completed card within 60 seconds of first app launch

### Progress & Analytics

- **FR41:** User can view a progress dashboard showing vocabulary size, cards learned, and review activity over time
- **FR42:** User can view per-session statistics (cards reviewed, correct rate, time spent)
- **FR43:** System tracks FSRS scheduling state per card and surfaces cards due for review

### Learner Intelligence

- **FR44:** System builds a continuous user knowledge profile based on vocabulary breadth, grammar forms encountered, practice performance, and recall history
- **FR45:** System evaluates and displays the user's estimated CEFR level (A1–C2) derived from their knowledge profile
- **FR46:** System displays a rich explanation of the assigned CEFR level — vocabulary ranges and grammar structures assessed, areas of confidence, and specific gaps to the next level
- **FR47:** User can view knowledge profile breakdown by category (vocabulary size, grammar coverage, pronunciation accuracy, active vs. passive recall)

### Data & Privacy

- **FR48:** All user data (cards, decks, progress, settings, credentials) is stored locally on the user's device
- **FR49:** System transmits no user data to external services beyond what the user explicitly configures (AI requests, speech evaluation)
- **FR50:** System filters AI-generated content (example sentences, images) through a safety check before display

## Non-Functional Requirements

### Performance

- Card creation pipeline: < 3 seconds end-to-end (OpenRouter); < 5 seconds (local Qwen fallback)
- Speech evaluation: < 2 seconds from utterance end to feedback display (Azure Speech or local Whisper)
- App shell initial load: < 2 seconds on desktop; < 4 seconds on mobile
- AI streaming: first token visible within 500ms of request
- Practice session UI: 60fps card transitions; optimistic updates; no blocking spinners
- Import processing: batch AI enrichment runs in background without blocking UI

### Security

- All credentials stored using OS keychain where available; encrypted local store as fallback — never plaintext
- Credentials never appear in application logs, error messages, or crash reports
- No telemetry, analytics, or usage data transmitted to any party — silent on the network except for explicit user-configured service calls

### Reliability

- All core features (card creation, practice, FSRS scheduling) function fully offline — network never required
- External service failures degrade gracefully — fall back to local models with clear user notification; sessions never crash or block
- All writes are durable before confirmation is shown to user — no data loss on crash

### Accessibility

- WCAG 2.1 AA compliance across all flows
- Full keyboard navigation — no mouse-only interactions
- Screen-reader compatibility for card creation, practice sessions, and settings
- Speak mode has a keyboard-accessible alternative for users without microphone access
- Color contrast minimum 4.5:1 for all text and UI elements

### Integration

- OpenRouter: standard REST API; supports model enumeration, streaming completions, connection testing
- Azure Speech: real-time speech recognition and pronunciation assessment APIs
- Local Qwen: Ollama-compatible local inference API
- Local Whisper: local process or server with stable API interface
- Image generation: configurable REST endpoint (OpenAI image generation API format)
- Anki import: `.apkg` and plain text/TSV deck formats

### Maintainability

- AI service abstraction: LLM and speech providers swappable behind a common interface — adding a new provider requires no changes to business logic
- Storage abstraction: data layer swappable between SQLite (desktop) and browser storage (web) without rewriting application logic
- Open-source contribution-friendly: consistent code style, documented public interfaces
