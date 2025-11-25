from typing import List
from openai import OpenAI
from app.core.config import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)  


async def summarize_messages(
    messages: List[tuple[str, str]],
    style: str = "short",
) -> str:
    """
    Summarize a list of messages.

    messages: list of (username, content)
    style: "short", "detailed", etc.
    """
    if not messages:
        return "No messages in this chat yet."

    # Build a simple transcript text
    transcript_lines = [
        f"{sender}: {content}" for sender, content in messages
    ]
    transcript = "\n".join(transcript_lines)

    prompt_style = {
        "short": "Give a short 2–3 sentence summary.",
        "detailed": "Give a detailed summary with main topics and decisions.",
    }.get(style, "Give a short 2–3 sentence summary.")

    system_msg = (
        "You are an assistant that summarizes chat conversations for users. "
        "Focus on the main topics, decisions, and action items, not small talk."
    )

    user_msg = (
        f"{prompt_style}\n\n"
        "Here is the chat transcript:\n\n"
        f"{transcript}"
    )

    # You can switch the model name to what you plan to use
    resp = client.chat.completions.create(
        model=settings.SUMMARIZER_MODEL,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=300,
        temperature=0.3,
    )

    summary = resp.choices[0].message.content.strip()
    return summary
