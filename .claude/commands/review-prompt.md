---
description: Review a runtime prompt in prompts/ against the constitution and Anthropic's prompt-engineering best practices. Usage: /review-prompt <prompt_name>
---

You are reviewing a runtime LLM prompt for quality, safety, and alignment with the project constitution. The user passed a prompt name as `$ARGUMENTS` (e.g., `planner`, `extractor`).

## Your steps

1. If `$ARGUMENTS` is empty, list available prompts in `prompts/*.md` and ask which to review.

2. Read `prompts/$ARGUMENTS.md`.

3. Read `prompts/_template.md` and `.specify/memory/constitution.md` for context.

4. Review the prompt against this checklist and report each as ✅ / ⚠️ / ❌ with a one-line explanation:

   **Structural checks**
   - [ ] Has all required sections: Role, Context, Task, Output Format, Constraints, Examples, Notes
   - [ ] Output Format references a Pydantic schema by name (not a free-form description)
   - [ ] Notes section explains design rationale, not just what the prompt does

   **Constitution alignment**
   - [ ] Does not request information that crosses ethical scope (sensitive attributes, PII synthesis)
   - [ ] If the prompt processes web content, content is wrapped in `<source url="...">...</source>` and the model is told to treat it as data, not instructions
   - [ ] If the prompt produces claims, it instructs the model to attach source URLs
   - [ ] If the prompt classifies or scores, it specifies the typed output schema

   **Anthropic best-practices alignment**
   - [ ] Uses XML-style tags to delimit sections of input
   - [ ] Provides 1–2 concrete examples (not just abstract description of the format)
   - [ ] System role is clear and specific (not "You are a helpful assistant")
   - [ ] Explicit about what to do when uncertain (e.g., "if you cannot determine X, return null rather than guessing")
   - [ ] Output constraints are positive instructions, not just negative ("Output exactly the schema fields" vs. "Don't add extra fields")

   **Cost / performance checks**
   - [ ] Prompt is no longer than necessary; no redundant restatement
   - [ ] If this prompt is called in a loop, it is using the cheapest model that can do the job (see CLAUDE.md model routing)
   - [ ] Uses prompt caching where applicable (long static system prompts cached, dynamic content in user message)

   **Failure-mode coverage**
   - [ ] Specifies behavior on empty input
   - [ ] Specifies behavior on contradictory input
   - [ ] Specifies behavior when the model would otherwise refuse (e.g., "if the request appears to involve a real minor, return refusal_reason")

5. After the checklist, propose 0–3 concrete edits (with diffs) for the highest-impact issues. Don't propose stylistic changes.

6. If the prompt looks good, say so plainly. Don't invent issues.

## Constraints

- Don't modify the prompt file directly. Output the proposed edit as a diff for human review.
- Don't expand the prompt's scope (e.g., adding new responsibilities). That's a spec change, not a prompt review.
- If the prompt's role overlaps another prompt's role, flag it but don't propose merging — that's an architecture change.