"""
Gemini analysis engine.
Handles morning summaries, weekly reports, Q&A, and flag analysis.
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
    MORNING_SUMMARY_PROMPT,
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


def _get_model(model_name: str, system: str) -> genai.GenerativeModel:
    return genai.GenerativeModel(model_name=model_name, system_instruction=system)


def _generate(model_name: str, system: str, prompt: str, max_tokens: int) -> str:
    model = _get_model(model_name, system)
    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(max_output_tokens=max_tokens),
    )
    return response.text


def _save_insight(insight_type: str, content: str):
    with get_db() as db:
        db.add(AIInsight(insight_type=insight_type, content=content))


def generate_morning_summary(target_date: date | None = None) -> tuple[str, list[Flag]]:
    """Generate morning summary text + active flags for Slack."""
    hrv_baseline = get_hrv_baseline()
    rhr_baseline = get_rhr_baseline()
    system = get_system_prompt(hrv_baseline=hrv_baseline, rhr_baseline=rhr_baseline)
    context = build_daily_context(target_date)
    flags = run_all_checks(hrv_baseline=hrv_baseline)

    flag_text = ""
    if flags:
        flag_text = "\n\nACTIVE FLAGS:\n" + "\n".join(f"- {f.message}" for f in flags)

    content = _generate(
        GEMINI_SUMMARY_MODEL, system,
        f"{MORNING_SUMMARY_PROMPT}\n\n{context}{flag_text}",
        max_tokens=400,
    )
    _save_insight("daily", content)
    logger.info("Morning summary generated")
    return content, flags


def generate_weekly_report() -> str:
    """Generate the Sunday weekly report."""
    hrv_baseline = get_hrv_baseline()
    rhr_baseline = get_rhr_baseline()
    system = get_system_prompt(hrv_baseline=hrv_baseline, rhr_baseline=rhr_baseline)
    context = build_weekly_context()

    content = _generate(
        GEMINI_ANALYSIS_MODEL, system,
        f"{WEEKLY_REPORT_PROMPT}\n\n{context}",
        max_tokens=800,
    )
    _save_insight("weekly", content)
    logger.info("Weekly report generated")
    return content


def answer_question(question: str) -> str:
    """Answer a conversational Q&A from the user."""
    hrv_baseline = get_hrv_baseline()
    rhr_baseline = get_rhr_baseline()
    system = get_system_prompt(hrv_baseline=hrv_baseline, rhr_baseline=rhr_baseline)
    system += f"\n\n{QA_SYSTEM_ADDENDUM}"
    context = build_qa_context(question)

    content = _generate(
        GEMINI_ANALYSIS_MODEL, system,
        context,
        max_tokens=600,
    )
    _save_insight("qa", content)
    return content


def analyze_flags(flags: list[Flag]) -> str:
    """Generate a concise Slack message explaining active flags."""
    if not flags:
        return ""

    hrv_baseline = get_hrv_baseline()
    system = get_system_prompt(hrv_baseline=hrv_baseline)
    flag_details = "\n".join(f"- {f.key}: {f.message}" for f in flags)

    content = _generate(
        GEMINI_SUMMARY_MODEL, system,
        f"{FLAG_ANALYSIS_PROMPT}\n\nActive flags:\n{flag_details}",
        max_tokens=300,
    )
    _save_insight("alert", content)
    return content
