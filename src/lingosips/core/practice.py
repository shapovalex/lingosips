"""Write-mode answer evaluation for lingosips practice.

Business logic only — no FastAPI imports.
API layer (api/practice.py) delegates here.
"""

import asyncio
import difflib
import json
from dataclasses import dataclass

import structlog

from lingosips.db.models import Card
from lingosips.services.llm.base import AbstractLLMProvider, LLMMessage

logger = structlog.get_logger(__name__)

LLM_TIMEOUT_SECONDS = 10.0
LLM_MAX_TOKENS = 64  # single-sentence explanation

SYSTEM_PROMPT = (
    "You are a concise language tutor. "
    "Given a vocabulary card, the user's written answer, and the correct answer, "
    "explain the specific error in one short sentence (max 15 words). "
    "Focus on grammar, spelling, or meaning. No preamble."
)


@dataclass
class CharHighlight:
    char: str
    correct: bool


@dataclass
class EvaluationResult:
    is_correct: bool
    highlighted_chars: list[CharHighlight]
    correct_value: str
    explanation: str | None
    suggested_rating: int  # 3=Good (correct), 1=Again (wrong)


def _char_diff(user_answer: str, correct_value: str) -> list[CharHighlight]:
    """Produce character-level diff between user_answer and correct_value.

    Uses difflib.SequenceMatcher for alignment. Characters matching the correct
    value are correct=True; extra/wrong characters are correct=False.
    Only covers chars from user_answer — insertions (chars missing from user) are omitted.

    Case-folded comparison is used for alignment so that correct letters typed in
    the wrong case are not marked as errors (consistent with the case-insensitive
    exact-match check in evaluate_answer). The display chars preserve original case.
    """
    # Fold case for alignment; display chars come from user_answer (original case).
    matcher = difflib.SequenceMatcher(
        None, user_answer.lower(), correct_value.lower(), autojunk=False
    )
    result: list[CharHighlight] = []
    for op, i1, i2, _j1, _j2 in matcher.get_opcodes():
        if op == "equal":
            for ch in user_answer[i1:i2]:  # original case preserved
                result.append(CharHighlight(char=ch, correct=True))
        elif op in ("replace", "delete"):
            for ch in user_answer[i1:i2]:  # original case preserved
                result.append(CharHighlight(char=ch, correct=False))
        # "insert" = chars in correct_value not typed by user — not added to display
    return result


SENTENCE_EVAL_SYSTEM_PROMPT = (
    "You are a language tutor evaluating sentence translations. "
    "Given a sentence card (target language), the student's English translation, "
    "and the reference translation, decide if the student's answer captures the meaning. "
    "Accept: same meaning in different words, minor grammatical variations, "
    "stylistic paraphrases. "
    "Reject: wrong meaning, missing key information, completely different tone. "
    "Return ONLY a JSON object: "
    '{"is_correct": true|false, "explanation": "one sentence or null"}. '
    "No markdown, no extra text."
)


async def _evaluate_sentence_answer(
    card: Card,
    user_answer: str,
    llm: AbstractLLMProvider,
) -> EvaluationResult:
    """LLM-based semantic evaluation for sentence/collocation cards.

    Does NOT produce char-level diff — highlighted_chars is always [].
    The LLM decides if the user's answer captures the meaning (paraphrase accepted).
    """
    correct_value = (card.translation or "").strip()
    normalized_user = user_answer.strip()

    # Exact match short-circuit (case-insensitive) — no LLM call
    if normalized_user.lower() == correct_value.lower():
        return EvaluationResult(
            is_correct=True,
            highlighted_chars=[],
            correct_value=correct_value,
            explanation=None,
            suggested_rating=3,
        )

    explanation: str | None = None
    is_correct = False

    try:
        messages: list[LLMMessage] = [
            {"role": "system", "content": SENTENCE_EVAL_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Sentence (target language): {card.target_word}\n"
                    f"Reference translation: {correct_value}\n"
                    f"Student answered: {normalized_user}"
                ),
            },
        ]
        raw = await asyncio.wait_for(
            llm.complete(messages, max_tokens=128),
            timeout=LLM_TIMEOUT_SECONDS,
        )
        # Parse LLM JSON response
        raw_stripped = raw.strip()
        if raw_stripped.startswith("```"):
            lines = raw_stripped.splitlines()
            end = next(
                (i for i, line in enumerate(lines[1:], 1) if line.strip() == "```"),
                len(lines),
            )
            raw_stripped = "\n".join(lines[1:end]).strip()
        start = raw_stripped.find("{")
        if start != -1:
            decoded = json.JSONDecoder().raw_decode(raw_stripped, start)[0]
            is_correct = bool(decoded.get("is_correct", False))
            expl = decoded.get("explanation")
            expl_str = str(expl).strip() if expl else ""
            is_null_sentinel = expl_str.lower() in ("null", "none")
            explanation = expl_str if expl_str and not is_null_sentinel else None
    except Exception as exc:
        logger.warning("llm_sentence_eval_failed", card_id=card.id, error=str(exc))
        is_correct = False
        explanation = None

    return EvaluationResult(
        is_correct=is_correct,
        highlighted_chars=[],  # never char-diff for sentence/collocation
        correct_value=correct_value,
        explanation=explanation,
        suggested_rating=3 if is_correct else 1,
    )


async def evaluate_answer(
    card: Card,
    user_answer: str,
    llm: AbstractLLMProvider,
) -> EvaluationResult:
    """Compare user's written answer to the card's translation and get AI feedback.

    For word cards: exact match check → char diff + LLM explanation on wrong answers.
    For sentence/collocation cards: LLM semantic evaluation (paraphrase accepted).
    """
    if card.card_type in ("sentence", "collocation"):
        return await _evaluate_sentence_answer(card, user_answer, llm)

    # Word card — existing exact-match + char-diff logic
    correct_value = (card.translation or "").strip()
    normalized_user = user_answer.strip()
    is_correct = normalized_user.lower() == correct_value.lower()

    highlighted_chars: list[CharHighlight] = (
        [] if is_correct else _char_diff(normalized_user, correct_value)
    )
    explanation: str | None = None

    if not is_correct:
        try:
            messages: list[LLMMessage] = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Word: {card.target_word}\n"
                        f"User answered: {normalized_user}\n"
                        f"Correct: {correct_value}"
                    ),
                },
            ]
            explanation = await asyncio.wait_for(
                llm.complete(messages, max_tokens=LLM_MAX_TOKENS),
                timeout=LLM_TIMEOUT_SECONDS,
            )
            explanation = explanation.strip() or None
        except Exception as exc:
            logger.warning("llm_evaluation_failed", card_id=card.id, error=str(exc))
            explanation = None  # session continues; user rates manually

    return EvaluationResult(
        is_correct=is_correct,
        highlighted_chars=highlighted_chars,
        correct_value=correct_value,
        explanation=explanation,
        suggested_rating=3 if is_correct else 1,
    )
