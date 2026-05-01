# Deployment Notes

This project is a Python + Streamlit app. For non-technical users, deploy the dashboard once and give them a web link.

## Public API-key policy

Public deployments should require each user to provide their own eBird API key. Do not deploy with a shared `EBIRD_API_KEY`.

Set this environment variable in hosted environments:

```bash
BBD_PUBLIC_DEPLOYMENT=1
```

When enabled, the dashboard does not read `EBIRD_API_KEY`, `.streamlit/secrets.toml`, or `ebird_token.json`. The key a user enters is used only by their Streamlit session to call eBird.

## Cloud Run

The included `Dockerfile` and deploy helper run Streamlit as a public Cloud Run service:

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
scripts/deploy_cloud_run.sh
```

Defaults:

- service: `big-day-optimizer`
- region: `us-east1`
- memory: `2Gi`
- CPU: `2`
- timeout: `900s`
- max instances: `3`
- env: `BBD_PUBLIC_DEPLOYMENT=1`
- public access: Cloud Run Invoker IAM check disabled with `--no-invoker-iam-check`

Override with environment variables, for example:

```bash
REGION=us-central1 MAX_INSTANCES=5 scripts/deploy_cloud_run.sh
```

For a custom subdomain such as `big-day.ellis-joyce.com`, create a Cloud Run domain mapping after deploy and follow the DNS instructions printed by Google Cloud:

```bash
gcloud beta run domain-mappings create \
  --service big-day-optimizer \
  --domain big-day.ellis-joyce.com \
  --region us-east1
```

## Streamlit Community Cloud

Alternative setup:

- Repository: `0xJustin/big_big_day`
- Branch: `main`
- Main file path: `dashboard.py`
- Python version: 3.10 or newer
- Environment or secret: `BBD_PUBLIC_DEPLOYMENT = "1"`

Steps:

1. Go to Streamlit Community Cloud and create a new app.
2. Select the GitHub repository.
3. Use `dashboard.py` as the app entrypoint.
4. Open the app secrets or environment settings.
5. Add:

```toml
BBD_PUBLIC_DEPLOYMENT = "1"
```

Streamlit will install from `requirements.txt`. The package metadata in `pyproject.toml` is included for local editable installs and CLI use.

## Add It To The Website

The website at `~/Projects/website` is an Astro/static site. Static sites can embed the running dashboard, but they cannot directly execute this optimizer because it needs Python, eBird API calls, and route solving on a server.

Use one of these options once the Streamlit app is deployed:

```html
<a href="https://your-streamlit-app-url">Open the Big Day Optimizer</a>
```

or:

```html
<iframe
  src="https://your-streamlit-app-url"
  style="width: 100%; min-height: 900px; border: 0;"
  title="Big Day Optimizer"
></iframe>
```

For an Astro page, create something like `src/pages/big-day.astro`:

```astro
---
const appUrl = "https://your-streamlit-app-url";
---

<main>
  <h1>Big Day Optimizer</h1>
  <iframe src={appUrl} title="Big Day Optimizer"></iframe>
</main>

<style>
  iframe {
    width: 100%;
    min-height: 900px;
    border: 0;
  }
</style>
```

## Local Release Check

Before pushing a release:

```bash
python -m unittest discover -s tests
pip install -e .
streamlit run dashboard.py
```

Confirm that `ebird_token.json` and `.streamlit/secrets.toml` are not staged.
