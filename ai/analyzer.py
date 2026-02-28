"""
Core Claude analysis engine.
Handles morning summaries, weekly reports, Q&A, and flag analysis.
"""

import logging
from datetime import date

import anthropic

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
    ANTHROPIC_API_KEY,
    CLAUDE_ANALYSIS_MODEL,
    CLAUDE_SUMMARY_MODEL,
)
from db.database import get_db
from db.models import AIInsight

logger = logging.getLogger(__name__)

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


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

    message = _client.messages.create(
        model=CLAUDE_SUMMARY_MODEL,
        max_tokens=400,
        system=system,
        messages=[{"role": "user", "content": f"{MORNING_SUMMARY_PROMPT}\n\n{context}{flag_text}"}],
    )
    content = message.content[0].text
    _save_insight("daily", content)
    logger.info("Morning summary generated")
    return content, flags


def generate_weekly_report() -> str:
    """Generate the Sunday weekly report."""
    hrv_baseline = get_hrv_baseline()
    rhr_baseline = get_rhr_baseline()
    system = get_system_prompt(hrv_baseline=hrv_baseline, rhr_baseline=rhr_baseline)
    context = build_weekly_context()

    message = _client.messages.create(
        model=CLAUDE_ANALYSIS_MODEL,
        max_tokens=800,
        system=system,
        messages=[{"role": "user", "content": f"{WEEKLY_REPORT_PROMPT}\n\n{context}"}],
    )
    content = message.content[0].text
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

    message = _client.messages.create(
        model=CLAUDE_ANALYSIS_MODEL,
        max_tokens=600,
        system=system,
        messages=[{"role": "user", "content": context}],
    )
    content = message.content[0].text
    _save_insight("qa", content)
    return content


def analyze_flags(flags: list[Flag]) -> str:
    """Generate a concise Slack message explaining active flags."""
    if not flags:
        return ""

    hrv_baseline = get_hrv_baseline()
    system = get_system_prompt(hrv_baseline=hrv_baseline)
    flag_details = "\n".join(f"- {f.key}: {f.message}" for f in flags)

    message = _client.messages.create(
        model=CLAUDE_SUMMARY_MODEL,
        max_tokens=300,
        system=system,
        messages=[{"role": "user", "content": f"{FLAG_ANALYSIS_PROMPT}\n\nActive flags:\n{flag_details}"}],
    )
    content = message.content[0].text
    _save_insight("alert", content)
    return content
