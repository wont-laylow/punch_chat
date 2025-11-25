from typing import Tuple
from transformers import pipeline

"""
Lightweight toxicity moderator using:

"""

_MODEL_NAME = "minuva/MiniLMv2-toxic-jigsaw"

# Load once at import time 
_classifier = pipeline(
    task="text-classification",
    model=_MODEL_NAME,
    truncation=True
)


TOXICITY_THRESHOLD = 0.5


def check_message_allowed_minilm(content: str) -> Tuple[bool, str | None]:
    """
    MiniLMv2-toxic-jigsaw to decide if a message is allowed.

    Returns:
        allowed: bool
        reason: Optional[str]  # non-None only when blocked
    """
    text = content.strip()
    if not text:
        # Empty / whitespace messages are allowed
        return True, None

   
    result = _classifier(text)[0]
    label: str = result["label"]
    score: float = float(result["score"])

    # High enough confidence is blocked.
    if label.lower() == "toxic" and score >= TOXICITY_THRESHOLD:
        reason = f"Blocked as toxic (score={score:.2f})"
        return False, reason

    return True, None


async def check_message_allowed(content: str) -> Tuple[bool, str | None]:
    """
    Async wrapper used by WebSocket / HTTP send endpoints.

    """
    # Being called directly
    return check_message_allowed_minilm(content)