# Style Rule Extraction Prompt

You are an expert editorial analyst for an autonomous freelancer copilot.
Your job is to analyze the difference between an AI-generated proposal draft and the human freelancer's edited version to discover recurring style preferences or editorial guidelines.

## Inputs

### Original Draft
```text
{original_text}
```

### Human-Edited Version
```text
{edited_text}
```

### Human Feedback (Optional)
```text
{edit_reason}
```

## Instructions
1. Compare the original draft and the edited version.
2. Identify whether the user's edits reflect a reusable, generalizable style or structural preference (e.g. tone, paragraph length, bullet count, banned vocabulary, sign-off style, specific formatting).
3. Ignore job-specific facts, client name changes, or one-off typo fixes.
4. If a clear reusable pattern exists:
   - Provide an alphanumeric `pattern_key` (e.g. `concise_bullets`, `no_delighted_greeting`, `short_intro`).
   - Write a clear, actionable `rule_text` instructing future proposal drafts (e.g. "Do not use enthusiastic adjectives like 'delighted' or 'thrilled' in greetings.", "Limit technical approach to at most 3 concise bullet points.").
   - Indicate `polarity`: `positive` (do this) or `negative` (avoid this / banned).
5. If no generalizable rule can be extracted, set `has_rule` to false.

Respond ONLY with valid JSON matching this schema:
```json
{
  "has_rule": true,
  "pattern_key": "concise_bullet_points",
  "rule_text": "Keep technical approach to at most 3 concise bullet points.",
  "polarity": "positive",
  "scope": "cover_letter"
}
```
