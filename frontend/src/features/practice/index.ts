/**
 * Public surface of the practice feature module.
 * Only export what other modules need — keep internals private.
 */

export { QueueWidget } from "./QueueWidget"
export { PracticeCard } from "./PracticeCard"
export { SessionSummary } from "./SessionSummary"
export { usePracticeSession } from "./usePracticeSession"
export type { QueueCard, SessionPhase, SessionSummary as SessionSummaryData, UsePracticeSessionReturn, EvaluationResult } from "./usePracticeSession"
export type { PracticeCardState } from "./PracticeCard"
export { SyllableFeedback } from "./SyllableFeedback"
export type { SyllableFeedbackState } from "./SyllableFeedback"
