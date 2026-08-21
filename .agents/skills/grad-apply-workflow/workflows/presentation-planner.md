# Presentation Planner

Goal: plan interview or advisor-meeting PPT content before passing it to a PPTX adapter.

## MVP Structure

Default 5-page structure:

1. Basic profile and application goal
2. Education background and strengths
3. Key research project
4. Fit with advisor direction
5. Future research plan and closing

## Protocol

1. Build a concise Markdown outline.
2. Keep each slide focused on one message.
3. Tie advisor-fit slides to advisor evidence.
4. Check page count, title length, and text density.
5. Use `LocalPptxAdapter` as MVP fallback.
6. Treat PPTAgent as optional future adapter, not copied project code.

## Guardrails

- Do not generate visual evidence that pretends to be real research output.
- Label AI-generated visual assets if image generation is ever used.
- Keep PPT content interview-explainable.
