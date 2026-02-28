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
Write Jay's weekly health report for Slack. Cover:

1. Recovery trends — what drove best/worst days this week
2. Journal correlations — how alcohol, stress, caffeine tracked with HRV/recovery
3. HRV trend vs previous 4-week average
4. Sleep debt balance (hours gained/lost)
5. Workout load vs recovery capacity — is he in balance or accumulating fatigue?
6. 1-2 actionable recommendations based on patterns

Be specific — use his actual numbers. Flag anything that needs attention.
Keep each section to 2-3 lines. Total should be under 30 lines.
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
