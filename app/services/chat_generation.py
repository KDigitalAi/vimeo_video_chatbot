"""
Prompt construction, response generation, and answer formatting helpers.
"""
from __future__ import annotations

from functools import lru_cache

from app.application.chat.policies import PDF_ONLY_REFUSAL_MESSAGE
from app.utils.runtime_helpers import get_logger_safe, get_settings_safe

logger = get_logger_safe(__name__)
settings = get_settings_safe()


@lru_cache(maxsize=4)
def _get_chat_llm(temperature: float):
    """Return a cached ChatOpenAI client for the given temperature."""
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=settings.LLM_MODEL, temperature=temperature)


def _follow_up_topic_hint(conversation_chain) -> str:
    """Best-effort last human message for follow-up grounding."""
    last_topic_text = None
    try:
        mem = conversation_chain.memory
        hist = mem.chat_memory.messages
        for i in range(len(hist) - 1, -1, -1):
            msg = hist[i]
            if hasattr(msg, "__class__") and "Human" in str(msg.__class__) and hasattr(msg, "content"):
                last_topic_text = msg.content
                break
    except Exception:
        last_topic_text = None
    return f"\nLast topic context: {last_topic_text}\n" if last_topic_text else "\n"


def _sorted_relevant_docs(relevant_docs: list) -> list:
    """Return docs sorted by score descending."""
    return sorted(relevant_docs, key=lambda item: item[1], reverse=True)


def _looks_already_structured(response_text: str) -> bool:
    text = (response_text or "").strip()
    if not text:
        return False
    if text == PDF_ONLY_REFUSAL_MESSAGE:
        return True
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    has_markdown_heading = any(
        line.startswith("# ") or line.startswith("## ") or line.startswith("### ")
        for line in lines
    )
    has_bold_section = any(
        line.startswith("**") and line.endswith("**")
        for line in lines
    )
    has_heading = has_markdown_heading or has_bold_section
    has_bullets = any(
        line.startswith("- ") or line.startswith("* ") or line.startswith("• ")
        for line in lines
    )
    has_numbered_list = any(
        line[:2].isdigit() or (
            len(line) > 2 and line[0].isdigit() and line[1:3] == ". "
        )
        for line in lines
    )
    has_code_block = "```" in text
    has_multiple_paragraphs = "\n\n" in text
    has_enough_length = len(text) >= 140
    has_sentence_density = text.count(". ") >= 2 or len(lines) >= 4
    has_sections = (
        "Concept:" in text
        and "Summary:" in text
        and ("Key Points:" in text or "Key points:" in text)
    ) or (
        "Explanation" in text and "Key Points" in text
    ) or (
        "Explanation" in text and "Example" in text
    )
    paragraph_count = len([p for p in text.split("\n\n") if p.strip()])
    return (
        has_heading
        or has_code_block
        or (has_sections and (has_bullets or has_numbered_list))
        or (has_heading and has_enough_length and has_sentence_density)
        or ((has_bullets or has_numbered_list) and paragraph_count >= 2)
        or (has_multiple_paragraphs and has_enough_length and has_sentence_density)
    )


def _format_educational_response(
    response_text: str,
    query: str,
    has_relevant_docs: bool = True,
    hybrid_weak_context: bool = False,
) -> str:
    _t = (response_text or "").strip()
    if _t.startswith("Sorry") and not has_relevant_docs:
        return PDF_ONLY_REFUSAL_MESSAGE
    if _looks_already_structured(_t):
        return _t
    if _t:
        return _t
    logger.warning(
        "Formatter received empty response text; returning local fallback shell (hybrid=%s, query=%s)",
        hybrid_weak_context,
        query[:80] if query else "",
    )
    return "Explanation:\nNo response content was generated."


def build_grounded_prompt(
    mode: str,
    context: str,
    query: str,
    *,
    topic_hint: str = "\n",
    is_follow_up: bool = False,
) -> str:
    if mode == "clarification":
        mode = "partial"
    if mode == "hybrid":
        mode = "partial"
    if mode not in ("partial", "strict"):
        raise ValueError(f"Unsupported grounded prompt mode: {mode}")

    context_block = f"{context}{topic_hint if is_follow_up else ''}".strip()

    return (
        "You are a tutor for software students.\n\n"
        "You must answer ONLY based on the provided PDF study materials.\n\n"
        "DECISION LOGIC (VERY IMPORTANT):\n\n"
        "Step 1: Determine if the question is related to the context.\n"
        "- If there is ANY relevant information in the context → it is RELATED.\n"
        "- Even a small or partial match = RELATED.\n\n"
        "Step 2: If RELATED:\n"
        "- Use the context as the primary source.\n"
        "- If the context is incomplete, use your knowledge to COMPLETE the answer.\n"
        "- Stay within the same topic.\n\n"
        "Step 3: If NOT RELATED:\n"
        "- This means NO relevant information exists in the context.\n"
        "- Do NOT answer.\n"
        "- Return exactly this single line and nothing else (no sections, no bullets):\n"
        f'"{PDF_ONLY_REFUSAL_MESSAGE}"\n\n'
        "IMPORTANT RULES:\n"
        "- Do NOT treat weak context as no context.\n"
        "- Even 1 relevant sentence = enough to answer.\n"
        "- Only refuse when context is completely unrelated.\n\n"
        "OUTPUT FORMAT (only when RELATED; plain text, no emojis):\n\n"
        "Concept:\n"
        "<short definition>\n\n"
        "Explanation:\n"
        "<simple explanation>\n\n"
        "Example:\n"
        "<example; use a fenced code block only if it helps>\n\n"
        "Key Points:\n"
        "- point 1\n"
        "- point 2\n"
        "- point 3\n\n"
        "Summary:\n"
        "<1-line summary>\n\n"
        "========================================\n"
        "CONTEXT\n"
        "========================================\n\n"
        f"{context_block}\n\n"
        "========================================\n"
        "QUESTION\n"
        "========================================\n\n"
        f"{query}"
    )


def _generate_clarification_response(query: str, relevant_docs: list) -> str:
    try:
        from langchain.schema import HumanMessage, SystemMessage

        context = _merge_and_clean_content(relevant_docs)
        system_prompt = build_grounded_prompt("clarification", context, query)
        llm = _get_chat_llm(0.4)
        messages = [SystemMessage(content=system_prompt), HumanMessage(content=query)]
        response = llm.invoke(messages)
        return response.content
    except Exception as e:
        logger.error(f"Error generating clarification response: {e}")
        return "I found relevant content but encountered an error explaining it. Please try rephrasing your question."


def _generate_weak_hybrid_response(query: str, relevant_docs: list) -> str:
    try:
        from langchain.schema import HumanMessage, SystemMessage

        context = _context_from_relevant_docs(relevant_docs)
        system_prompt = build_grounded_prompt("hybrid", context, query)
        llm = _get_chat_llm(0.35)
        messages = [SystemMessage(content=system_prompt), HumanMessage(content=query)]
        return llm.invoke(messages).content
    except Exception as e:
        logger.error(f"Error generating weak hybrid response: {e}")
        return "I found related material but could not complete the answer. Please try again."


def _generate_context_grounded_response(
    query: str,
    context: str,
    *,
    is_hybrid_context: bool = False,
    is_follow_up: bool = False,
    topic_hint: str = "\n",
) -> str:
    try:
        from langchain.schema import HumanMessage, SystemMessage

        prompt = build_grounded_prompt(
            "partial" if is_hybrid_context else "strict",
            context,
            query,
            topic_hint=topic_hint,
            is_follow_up=is_follow_up,
        )
        llm = _get_chat_llm(0.35 if is_hybrid_context else 0.2)
        messages = [
            SystemMessage(
                content=(
                    "Follow the user message. Answer ONLY from PDF context when stating facts; "
                    "partial or weak context still counts as RELATED. Refuse only when fully unrelated. "
                    "If unrelated, output only the exact refusal line. If related, use the section format. "
                    "No emojis."
                    if is_hybrid_context
                    else "Follow the user message. Answer ONLY from PDF context when stating facts; "
                    "partial or weak context still counts as RELATED. Refuse only when fully unrelated. "
                    "If unrelated, output only the exact refusal line. If related, ground in the Context "
                    "then use the section format. No emojis."
                )
            ),
            HumanMessage(content=prompt),
        ]
        return llm.invoke(messages).content
    except Exception as e:
        logger.error(f"Error generating context-grounded response: {e}")
        raise


def _merge_and_clean_content(relevant_docs: list, *, sorted_docs: list | None = None) -> str:
    pdf_content = []
    sorted_docs = sorted_docs or _sorted_relevant_docs(relevant_docs)
    for doc, score in sorted_docs:
        content = doc.page_content.strip()
        if not content:
            continue
        metadata = getattr(doc, "metadata", {})
        source_type = metadata.get("source_type", "pdf")
        if source_type != "pdf":
            continue
        cleaned_content = content.replace("\n", " ").replace("  ", " ").strip()
        cleaned_content = " ".join(cleaned_content.split())
        pdf_title = metadata.get("pdf_title", "Unknown PDF")
        page = metadata.get("page_number", "?")
        pdf_content.append(f"[PDF: {pdf_title}, Page {page}] {cleaned_content}")
    combined_content = []
    if pdf_content:
        combined_content.append("PDF study materials:")
        combined_content.append("\n".join(pdf_content))
    if combined_content:
        combined_content.append("\nInstructions for the tutor:")
        combined_content.append(
            "Use the excerpts above as the primary source. Any relevant snippet counts as "
            "related context; follow the DECISION LOGIC in the main prompt."
        )
    return "\n\n".join(combined_content)


def _context_from_relevant_docs(relevant_docs: list) -> str:
    sorted_docs = _sorted_relevant_docs(relevant_docs)
    merged = _merge_and_clean_content(relevant_docs, sorted_docs=sorted_docs)
    if (merged or "").strip():
        return merged
    parts = []
    for doc, _score in sorted_docs:
        raw = (getattr(doc, "page_content", None) or "").strip()
        if raw:
            parts.append(raw)
    return "\n\n".join(parts)[:12000]


def build_follow_up_topic_hint(conversation_chain) -> str:
    return _follow_up_topic_hint(conversation_chain)


def looks_already_structured(response_text: str) -> bool:
    return _looks_already_structured(response_text)


def format_educational_response(
    response_text: str,
    query: str,
    has_relevant_docs: bool = True,
    hybrid_weak_context: bool = False,
) -> str:
    return _format_educational_response(
        response_text,
        query,
        has_relevant_docs=has_relevant_docs,
        hybrid_weak_context=hybrid_weak_context,
    )


def generate_clarification_response(query: str, relevant_docs: list) -> str:
    return _generate_clarification_response(query, relevant_docs)


def generate_weak_hybrid_response(query: str, relevant_docs: list) -> str:
    return _generate_weak_hybrid_response(query, relevant_docs)


def generate_context_grounded_response(
    query: str,
    context: str,
    *,
    is_hybrid_context: bool = False,
    is_follow_up: bool = False,
    topic_hint: str = "\n",
) -> str:
    return _generate_context_grounded_response(
        query,
        context,
        is_hybrid_context=is_hybrid_context,
        is_follow_up=is_follow_up,
        topic_hint=topic_hint,
    )


def merge_and_clean_content(relevant_docs: list) -> str:
    return _merge_and_clean_content(relevant_docs)


def build_context_from_docs(relevant_docs: list) -> str:
    return _context_from_relevant_docs(relevant_docs)

