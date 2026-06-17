# Retrospective

## What Went Well

- Logos-Log grew from a RAG chat prototype into a fuller meaning action loop: journal entry, evidence-backed reflection, value card capture, weekly experiment recommendation, and later reflection.
- The product became more honest about what the AI can support. The UI says `근거 발췌` rather than claiming whole-paper summaries, and the README records that Faithfulness is still the next quality target.
- Safety and operations became part of the product rather than an afterthought: refresh-token rotation, CSRF origin checks, rate limiting, structured logs, request IDs, and copy-quality guardrails are now covered by tests.
- Evaluation results shaped product decisions. `$text` hybrid/RRF search stayed out of the production default because the recorded evaluations did not justify switching away from vector-only retrieval.

## What Was Difficult

- RAG quality work was uneven. Retrieval precision and recall improved enough to pass the accepted run, but Faithfulness lagged behind the target.
- The heaviest dependencies, especially local embeddings and MongoDB Atlas Vector Search, make full end-to-end evaluation more expensive than a normal unit-test loop.
- Final submission evidence lives across product code, assignments, workflows, dashboards, and documents, so it needed an explicit final-submission layer to make the project reviewable.
- Deployment proof depends on external systems: GitHub Actions secrets, Vercel project state, Render service state, and a manually recorded demo video.

## What Changed

- Added a dependency-free `/health` endpoint so deployment health checks do not rely on MongoDB, OpenAI, or model warmup.
- Added a final GitHub Actions gate that runs frontend quality checks and AI mini evals on PRs and main pushes.
- Expanded Dependabot from assignment-only coverage to the production frontend and backend.
- Added `RUNBOOK.md`, `CHANGELOG.md`, and this retrospective so operating, releasing, and reviewing the project do not depend on tribal knowledge.

## Lessons Learned

- RAG systems need product copy that matches the actual evidence boundary. A trustworthy UI is partly an engineering artifact.
- Small deterministic evals are valuable even when full RAG evals are expensive. They catch safety and recommendation regressions quickly enough to run on every PR.
- A final project is easier to evaluate when each requirement has a stable URL, command, or file path.
- Release readiness is not just "the app works"; it includes rollback, health checks, observability, documentation, and a demo path another person can follow.

## Next Improvements

- Improve Faithfulness with sentence-level evidence checks that do not destabilize answer relevancy.
- Add a lightweight backend integration test gate once CI dependency install time is acceptable.
- Publish the DORA dashboard through GitHub Pages after Pages is enabled for the repository.
- Attach the final under-3-minute demo video to the `v1.0.0` GitHub Release.
