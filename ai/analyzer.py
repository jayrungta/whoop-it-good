"""
Gemini analysis engine.
"""

import logging
from datetime import date

import google.generativeai as genai

from ai.context import (
    build_daily_context,
    build_qa_context,
    build_weekly_context,
    get_hrv_baseline,
    get_rhr_baseline,
)
from ai.flags import Flag, run_all_checks
from ai.prompts import (
    FLAG_ANALYSIS_PROMPT,
    QA_SYSTEM_ADDENDUM,
    WEEKLY_REPORT_PROMPT,
)
from config.personal_context import get_system_prompt
from config.settings import (
    GEMINI_API_KEY,
    GEMINI_ANALYSIS_MODEL,
    GEMINI_SUMMARY_MODEL,
)
from db.database import get_db
from db.models import AIInsight

logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_API_KEY)


def _generate(model_name: str, system: str, prompt: str, max_tokens: int = 8192) -> str:
    model = genai.GenerativeModel(model_name=model_name, system_instruction=system)
    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(max_output_tokens=max_tokens),
    )
    return response.text


def _save_insight(insight_type: str, content: str):
    with get_db() as db:
        db.add(AIInsight(insight_type=insight_type, content=content))


def generate_daily_insight(context: str, flags: list[Flag]) -> str:
    """
    Returns 1-2 sentences of insight only — no formatting, no metrics.
    morning.py handles layout; this just adds the AI angle.
    """
    hrv_baseline = get_hrv_baseline()
    rhr_baseline = get_rhr_baseline()
    system = get_system_prompt(hrv_baseline=hrv_baseline, rhr_baseline=rhr_baseline)

    flag_text = ""
    if flags:
        flag_text = "\n\nActive flags:\n" + "\n".join(f"- {f.message}" for f in flags)

    prompt = (
        "Based on today's data, give Jay one sharp observation and one concrete action for today. "
        "Max 2 sentences. Lead with the most important signal. Skip anything obvious. "
        "No fluff, no 'your recovery is X%' restatements — he can already see the numbers.\n\n"
        f"{context}{flag_text}"
    )

    content = _generate(GEMINI_SUMMARY_MODEL, system, prompt, max_tokens=8192)
    _save_insight("daily", content)
    logger.info("Daily insight generated")
    return content.strip()


def generate_weekly_report() -> str:
    hrv_baseline = get_hrv_baseline()
    rhr_baseline = get_rhr_baseline()
    system = get_system_prompt(hrv_baseline=hrv_baseline, rhr_baseline=rhr_baseline)
    context = build_weekly_context()

    content = _generate(
        GEMINI_ANALYSIS_MODEL, system,
        f"{WEEKLY_REPORT_PROMPT}\n\n{context}",
        max_tokens=8192,
    )
    _save_insight("weekly", content)
    logger.info("Weekly report generated")
    return content


def answer_question(question: str) -> str:
    hrv_baseline = get_hrv_baseline()
    rhr_baseline = get_rhr_baseline()
    system = get_system_prompt(hrv_baseline=hrv_baseline, rhr_baseline=rhr_baseline)
    system += f"\n\n{QA_SYSTEM_ADDENDUM}"
    context = build_qa_context(question)

    content = _generate(GEMINI_ANALYSIS_MODEL, system, context, max_tokens=8192)
    _save_insight("qa", content)
    return content


def analyze_flags(flags: list[Flag]) -> str:
    if not flags:
        return ""

    hrv_baseline = get_hrv_baseline()
    system = get_system_prompt(hrv_baseline=hrv_baseline)
    flag_details = "\n".join(f"- {f.key}: {f.message}" for f in flags)

    content = _generate(
        GEMINI_SUMMARY_MODEL, system,
        f"{FLAG_ANALYSIS_PROMPT}\n\nActive flags:\n{flag_details}",
        max_tokens=8192,
    )
    _save_insight("alert", content)
    return content
