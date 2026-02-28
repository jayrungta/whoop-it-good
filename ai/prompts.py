"""Reusable prompt templates for Claude API calls."""

MORNING_SUMMARY_PROMPT = """
Based on Jay's biometric data, write a concise morning health summary for Slack.

FORMAT (follow exactly, no markdown headers):
- Line 1: Recovery score with color emoji (🟢 ≥67%, 🟡 34–66%, 🔴 ≤33%)
- Line 2: HRV vs baseline
- Line 3: Sleep breakdown (total hours, % deep, % REM)
- Line 4: Blank line
- Line 5: 1–2 sentence insight referencing his specific numbers and any patterns
- Line 6: Any active flags (if none, omit this line)

Keep it under 8 lines total. No bullet points. No markdown. Plain text only.
""".strip()

WEEKLY_REPORT_PROMPT = """
Write Jay's weekly health report for Slack. Use this exact format:

*Recovery* — one sentence on best/worst days and what drove them. Include scores.
*HRV* — weekly avg vs 4-week avg, direction of trend. One sentence.
*Sleep* — avg hours, debt balance, worst night. One sentence.
*Lifestyle* — any journal correlations worth calling out (alcohol, stress, caffeine vs HRV). One sentence. Skip if no journal data.
*Training* — workout load vs recovery capacity. One sentence.
*This week* — 2 bullet points max, the most actionable things he should do differently. Lead each with a verb.

Rules:
- Use Slack bold (*text*) for section labels only
- Each section is one sentence, max two. No paragraphs.
- Skip any section with no data
- Use his actual numbers throughout
- No intro, no outro, no "here is your report"
""".strip()

QA_SYSTEM_ADDENDUM = """
The user is asking a direct health question. Answer conversationally but with precision.
Reference specific data points from the context provided. If the data doesn't support
a confident answer, say so. Never give generic health advice — only insights grounded
in Jay's actual numbers.
""".strip()

FLAG_ANALYSIS_PROMPT = """
Analyze these active health flags for Jay. For each flag, explain:
1. What the data shows (specific numbers)
2. Why it matters for him specifically
3. One concrete action for today

Write as plain text for Slack. No headers. Under 10 lines total.
""".strip()
