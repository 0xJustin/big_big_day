# Deployment Notes

This project is a Python + Streamlit app. For non-technical users, deploy the dashboard once and give them a web link.

## Streamlit Community Cloud

Recommended setup:

- Repository: `0xJustin/big_big_day`
- Branch: `main`
- Main file path: `dashboard.py`
- Python version: 3.10 or newer
- Secret: `EBIRD_API_KEY`

Steps:

1. Go to Streamlit Community Cloud and create a new app.
2. Select the GitHub repository.
3. Use `dashboard.py` as the app entrypoint.
4. Open the app secrets settings.
5. Add:

```toml
EBIRD_API_KEY = "paste-your-ebird-api-key-here"
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
