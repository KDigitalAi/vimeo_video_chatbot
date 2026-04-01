"""
Prompt construction, response generation, and answer formatting helpers.
"""
from __future__ import annotations

from app.utils.runtime_helpers import get_logger_safe, get_settings_safe

logger = get_logger_safe(__name__)
settings = get_settings_safe()

PDF_ONLY_REFUSAL_MESSAGE = (
    "Sorry, I can only answer based on the available PDF study materials."
)


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
    return f"\n🧭 **Last Topic Context:** {last_topic_text}\n" if last_topic_text else "\n"


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
    return "**Explanation:**\nNo response content was generated."


def build_grounded_prompt(
    mode: str,
    context: str,
    query: str,
    *,
    topic_hint: str = "\n",
    is_follow_up: bool = False,
) -> str:
    if mode == "clarification":
        return f"""You are an expert programming instructor helping a student who needs extra clarification. Your goal is to make complex concepts crystal clear through detailed, step-by-step explanations using ONLY the course materials provided.

🎯 **CLARIFICATION MISSION:**
This student specifically asked for clarification, so they need extra help, encouragement, and detailed explanations.

📋 **TEACHING APPROACH:**
1. **Use ONLY the information from the provided course materials below**
2. **Break down the concept into simple, digestible steps**
3. **Use analogies only when they restate ideas explicitly stated in the materials** (no outside topics)
4. **Use encouraging, supportive language** throughout
5. **Include practical code examples with detailed comments**
6. **Address common student misconceptions** about this topic
7. **Focus on clear, detailed explanations** that build understanding
8. **Structure your response with clear sections:**
   - **What is it?** Simple, clear definition
   - **How does it work?** Step-by-step breakdown
   - **Step-by-step Example:** Detailed example with code
   - **Why is it important?** Practical applications and benefits
   - **Key Takeaway:** Summary and encouragement

📚 **COURSE MATERIALS TO USE:**
{context}

🎓 **STUDENT-FOCUSED CLARIFICATION:**
- Think like a patient teaching assistant who loves helping students
- Use "Let's break this down together" approach
- Provide multiple examples if available in the materials
- Explain the "why" behind each step
- Encourage questions and further learning
- Make complex concepts feel approachable

Remember: This student asked for clarification, so they need extra help, encouragement, and comprehensive explanations!

OUTPUT FORMAT (FINAL ANSWER FORMAT):
- Return the final answer directly in GitHub-flavored markdown.
- Unless the correct answer is the exact refusal sentence, make the response production-ready on the FIRST pass so no extra formatting is needed.
- Use `### Explanation`, `### Example`, and `### Key Points` whenever content allows.
- Put blank lines between sections.
- Use markdown bullet points for key points.
- Use fenced ```python code blocks with real newlines and indentation for code.

STRICT GROUNDING (MANDATORY):
- Answer ONLY from the course materials above. Do not use other programming languages, libraries, or facts not present in the text.
- If the materials are weak or partial, still provide the best possible answer grounded strictly in the available context.
- Be explicit about limits with one short note like: "Based on the available material, this answer may be partial."
- Refusal is allowed ONLY when no context is provided at all."""
    if mode == "hybrid":
        return f"""📚 **PDF CONTEXT (BASE — may be partial; answer must start here):**
{context}{topic_hint if is_follow_up else ""}

❓ **{'STUDENT FOLLOW-UP' if is_follow_up else 'STUDENT QUESTION'}:** {query}

🎯 **HYBRID MODE (scores in partial-relevance band)**
- Begin with: "Based on the available material, ..." and summarize what the PDF excerpts support.
- If the excerpts only partially answer the question, add widely accepted completion after: "Additionally, in general, ...".
- Do NOT use general knowledge to answer a completely different topic than the PDFs (e.g. another language not in the materials). If excerpts do not address the question, reply ONLY with exactly: {PDF_ONLY_REFUSAL_MESSAGE}
- Do not contradict the PDF where it is specific.
- Return the final answer directly in GitHub-flavored markdown using `### Explanation`, `### Example`, and `### Key Points` when applicable.
- Make this first response already well-formatted enough to send directly without any second formatting pass.
- Put blank lines between sections and use fenced ```python code blocks for code."""
    if mode == "strict":
        if is_follow_up:
            return f"""📚 **COURSE MATERIALS CONTEXT (ONLY SOURCE OF TRUTH):**
{context}{topic_hint}
❓ **STUDENT FOLLOW-UP QUESTION:** {query}

🎯 **INSTRUCTIONS:**
This is a follow-up. Use ONLY the course materials above. Do NOT use outside knowledge, other textbooks, or another programming language unless it literally appears in the context.
If the question is clearly about a different topic than the materials, reply ONLY with exactly: {PDF_ONLY_REFUSAL_MESSAGE}
Stay on topic, do not contradict the materials.
Return the final answer directly in GitHub-flavored markdown using `### Explanation`, `### Example`, and `### Key Points` when applicable.
Make this first response already well-formatted enough to send directly without any second formatting pass.
Put blank lines between sections and use fenced ```python code blocks with real newlines for code."""
        return f"""📚 **COURSE MATERIALS CONTEXT (ONLY SOURCE OF TRUTH):**
{context}

❓ **STUDENT QUESTION:** {query}

🎯 **INSTRUCTIONS:**
Answer ONLY using the course materials above. Do NOT guess, do NOT use general knowledge, and do NOT introduce programming languages or APIs not evidenced in the context.
If the question is clearly about a different topic than the materials (e.g. another programming language not present), reply ONLY with exactly: {PDF_ONLY_REFUSAL_MESSAGE}
Give a clear educational answer.
Return the final answer directly in GitHub-flavored markdown using `### Explanation`, `### Example`, and `### Key Points` when applicable.
Make this first response already well-formatted enough to send directly without any second formatting pass.
Put blank lines between sections and use fenced ```python code blocks with real newlines for code."""
    raise ValueError(f"Unsupported grounded prompt mode: {mode}")


def _generate_clarification_response(query: str, relevant_docs: list) -> str:
    try:
        from langchain_openai import ChatOpenAI
        from langchain.schema import HumanMessage, SystemMessage

        context = _merge_and_clean_content(relevant_docs)
        system_prompt = build_grounded_prompt("clarification", context, query)
        llm = ChatOpenAI(model=settings.LLM_MODEL, temperature=0.4)
        messages = [SystemMessage(content=system_prompt), HumanMessage(content=query)]
        response = llm.invoke(messages)
        return response.content
    except Exception as e:
        logger.error(f"Error generating clarification response: {e}")
        return "I found relevant content but encountered an error explaining it. Please try rephrasing your question."


def _generate_weak_hybrid_response(query: str, relevant_docs: list) -> str:
    try:
        from langchain_openai import ChatOpenAI
        from langchain.schema import HumanMessage, SystemMessage

        context = _context_from_relevant_docs(relevant_docs)
        system_prompt = build_grounded_prompt("hybrid", context, query)
        llm = ChatOpenAI(model=settings.LLM_MODEL, temperature=0.35)
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
        from langchain_openai import ChatOpenAI
        from langchain.schema import HumanMessage, SystemMessage

        prompt = build_grounded_prompt(
            "hybrid" if is_hybrid_context else "strict",
            context,
            query,
            topic_hint=topic_hint,
            is_follow_up=is_follow_up,
        )
        llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            temperature=0.35 if is_hybrid_context else 0.2,
        )
        messages = [
            SystemMessage(content="You are a careful RAG assistant. Answer only from the provided context and follow the user's instructions exactly."),
            HumanMessage(content=prompt),
        ]
        return llm.invoke(messages).content
    except Exception as e:
        logger.error(f"Error generating context-grounded response: {e}")
        raise


def _merge_and_clean_content(relevant_docs: list) -> str:
    pdf_content = []
    sorted_docs = sorted(relevant_docs, key=lambda x: x[1], reverse=True)
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
        combined_content.append("📚 **PDF Course Materials:**")
        combined_content.append("\n".join(pdf_content))
    if combined_content:
        combined_content.append("\n**Instructions for Response:**")
        combined_content.append("Use ALL the information above to provide a complete, comprehensive explanation. Structure your response with clear explanations, practical examples, and key takeaways.")
    return "\n\n".join(combined_content)


def _context_from_relevant_docs(relevant_docs: list) -> str:
    merged = _merge_and_clean_content(relevant_docs)
    if (merged or "").strip():
        return merged
    parts = []
    for doc, _score in sorted(relevant_docs, key=lambda x: x[1], reverse=True):
        raw = (getattr(doc, "page_content", None) or "").strip()
        if raw:
            parts.append(raw)
    return "\n\n".join(parts)[:12000]

