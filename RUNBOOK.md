# Logos-Log Runbook

This runbook covers the production-facing release flow for the final Logos-Log submission: Vercel frontend, Render backend, health checks, rollback, and observability.

## Production Links

| Surface | Location |
|---|---|
| GitHub repository | https://github.com/alsrjs951/Logos-Log |
| Frontend production | https://frontend-eight-nu-21.vercel.app |
| Backend production | `RENDER_BACKEND_URL` GitHub Actions secret |
| Backend health check | `${RENDER_BACKEND_URL}/health` |
| DORA metrics workflow | https://github.com/alsrjs951/Logos-Log/actions/workflows/metrics.yml |
| Final submission gate | https://github.com/alsrjs951/Logos-Log/actions/workflows/final-submission-gate.yml |

## Required Secrets

Set these in GitHub Actions before the final main deployment:

| Secret | Used by | Purpose |
|---|---|---|
| `VERCEL_TOKEN` | `week10-frontend-deploy.yml` | Deploy frontend to Vercel |
| `VERCEL_ORG_ID` | `week10-frontend-deploy.yml` | Select Vercel team/account |
| `VERCEL_PROJECT_ID` | `week10-frontend-deploy.yml` | Select frontend project |
| `RENDER_DEPLOY_HOOK_URL` | `week10-backend-deploy.yml` | Trigger Render deploy |
| `RENDER_BACKEND_URL` | `week10-backend-deploy.yml` | Verify live backend `/health` |

Backend runtime secrets must be configured in Render:

```bash
MONGODB_URI=mongodb+srv://...
OPENAI_API_KEY=sk-...
JWT_SECRET=<long random value>
ENCRYPTION_KEY=<32-byte urlsafe base64 value>
CORS_ALLOW_ORIGINS=https://frontend-eight-nu-21.vercel.app
REFRESH_COOKIE_SECURE=true
REFRESH_COOKIE_SAMESITE=none
STRUCTURED_LOGS_ENABLED=true
APP_VERSION=v1.0.0
```

Generate an encryption key:

```bash
python -c "import os,base64;print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
```

## Deploy

1. Open a PR into `main`.
2. Confirm `Final Submission Gate` passes:
   - frontend lint
   - frontend unit tests
   - frontend production build
   - crisis detection mini eval
   - meaning experiment recommendation mini eval
3. Merge to `main`.
4. Confirm frontend deploy:
   - workflow: `Week 10 Frontend Deployment & PR Preview`
   - expected public URL: `https://frontend-eight-nu-21.vercel.app`
5. Confirm backend deploy:
   - workflow: `Week 10 Backend Deployment & Live Healthcheck`
   - expected health URL: `${RENDER_BACKEND_URL}/health`

Manual smoke checks:

```bash
curl -fsS "${RENDER_BACKEND_URL%/}/health"
curl -I https://frontend-eight-nu-21.vercel.app
```

Expected backend response:

```json
{
  "status": "ok",
  "service": "logos_log",
  "version": "v1.0.0"
}
```

## Rollback

Use the smallest rollback that restores service.

1. If the frontend is broken, promote the previous successful Vercel deployment or revert the merge commit and let the frontend workflow redeploy.
2. If the backend is broken, redeploy the previous Render deploy from the Render dashboard. If needed, retag or redeploy the previous GHCR image SHA.
3. If the issue is configuration-only, restore the previous Render/Vercel environment variables and redeploy without code changes.
4. Verify recovery:

```bash
curl -fsS "${RENDER_BACKEND_URL%/}/health"
```

5. Open a GitHub issue labeled `incident` and record:
   - failing commit SHA
   - detection time
   - rollback action
   - recovery time
   - user-visible impact

The week 11 canary rollback simulator remains as a documented rollback exercise:

```bash
./assignments/week11/scripts/canary-rollout.sh healthy
./assignments/week11/scripts/canary-rollout.sh unhealthy
```

## Observability

Application logs are structured JSON when `STRUCTURED_LOGS_ENABLED=true`.

Important fields:

| Field | Meaning |
|---|---|
| `request_id` | Correlates frontend requests, backend logs, and error reports |
| `event` | Machine-readable event name |
| `level` | `info`, `warning`, or `error` |
| `path` / `status_code` / `latency_ms` | Request completion telemetry |
| `*_hash` | Hashed user, journal, intention, card, token, or email identifiers |

Events to watch:

| Event | Action |
|---|---|
| `request_unhandled_error` | Check stack trace and correlated `request_id` |
| `rag_stream_error` | Check OpenAI/MongoDB availability and rate limits |
| `recommended_experiment_error` | Check LLM timeout or copy quality guardrail failure |
| `csrf_origin_rejected` | Confirm frontend origin and trusted origin config |
| `meaning_experiment_adopted` / `reflected` / `dismissed` | Product loop adoption and completion signals |

DORA metrics are collected by `.github/workflows/metrics.yml`. The static dashboard source is `dashboard/index.html`, and `.github/workflows/deploy-dashboard.yml` publishes it to GitHub Pages when Pages is enabled.

For local log analysis:

```bash
docker compose -f docker-compose-es.yml up -d
```

## Release Checklist

Run these after the final PR is merged and the demo video file exists:

```bash
git fetch origin main --tags
git checkout main
git pull --ff-only origin main
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
gh release create v1.0.0 logos-log-demo-v1.0.0.mp4 \
  --repo alsrjs951/Logos-Log \
  --title "Logos-Log v1.0.0" \
  --notes-file CHANGELOG.md
```

The demo video must be under 3 minutes and should cover:

1. Open the deployed frontend.
2. Create or sign into an account.
3. Write a journal entry.
4. Run the AI reflection chat and open source evidence.
5. Save a value card.
6. Adopt a recommended experiment.
7. Show the dashboard action loop.
