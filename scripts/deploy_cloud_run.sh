#!/usr/bin/env bash
set -euo pipefail

service="${SERVICE_NAME:-big-day-optimizer}"
region="${REGION:-us-east1}"
project="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
env_vars="BBD_PUBLIC_DEPLOYMENT=1"

if [ -n "${STREAMLIT_APP:-}" ]; then
  env_vars="${env_vars},STREAMLIT_APP=${STREAMLIT_APP}"
fi

if [ -z "$project" ]; then
  echo "Set PROJECT_ID or run: gcloud config set project YOUR_PROJECT_ID" >&2
  exit 1
fi

gcloud run deploy "$service" \
  --project "$project" \
  --region "$region" \
  --source . \
  --no-invoker-iam-check \
  --port 8501 \
  --memory "${MEMORY:-2Gi}" \
  --cpu "${CPU:-2}" \
  --concurrency "${CONCURRENCY:-4}" \
  --max-instances "${MAX_INSTANCES:-3}" \
  --timeout "${TIMEOUT:-900}" \
  --set-env-vars "$env_vars"
