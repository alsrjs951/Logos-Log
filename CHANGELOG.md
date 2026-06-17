# Changelog

All notable changes to Logos-Log are documented here.

## v1.0.0 - 2026-06-17

### Added

- Final submission gate for pull requests and main pushes.
- Dependency-free backend `GET /health` endpoint for Render live checks.
- Frontend lint, unit test, and production build gate.
- AI mini eval gate for crisis detection and meaning experiment recommendation quality.
- Final runbook, release checklist, changelog, and retrospective.
- Dependabot coverage for frontend npm, backend pip, GitHub Actions, and the historical week 9 package.

### Changed

- Backend deployment workflow now verifies `${RENDER_BACKEND_URL}/health` after Render deploy.
- Frontend quality workflow now runs unit tests before build.
- README now groups final submission evidence, deployment links, CI/CD, observability, release, and demo video status.

### Operational Notes

- Production frontend target: https://frontend-eight-nu-21.vercel.app
- Production backend health target: `${RENDER_BACKEND_URL}/health`
- Release tag: `v1.0.0`
- Release asset expected for final submission: `logos-log-demo-v1.0.0.mp4`

### Known Follow-ups

- Upload the under-3-minute demo video to the `v1.0.0` GitHub Release.
