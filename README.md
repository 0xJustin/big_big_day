# Big Day Optimizer

Plan a one-day eBird route for a region and date. The optimizer uses eBird checklist frequencies, hotspot locations, estimated drive time, stop limits, and species-level probabilities across the full route.

## What You Need

- Python 3.10+
- An eBird API key: https://support.ebird.org/en/support/solutions/articles/48000838205-download-ebird-data

## Run The Dashboard

Using `uv`:

```bash
git clone https://github.com/0xJustin/big_big_day.git
cd big_big_day
uv venv
source .venv/bin/activate
uv pip install -e .
streamlit run dashboard.py
```

Using `pip`:

```bash
git clone https://github.com/0xJustin/big_big_day.git
cd big_big_day
python -m venv .venv
source .venv/bin/activate
pip install -e .
streamlit run dashboard.py
```

On Windows:

```powershell
.venv\Scripts\activate
```

Paste your eBird API key into the dashboard, choose a region and date, then run the optimizer.

## Migrant Hotspot Dashboard

The repo also includes a warbler migration dashboard. It ranks county hotspots by warbler variety, warbler abundance, time of day, and a best-effort photo signal when checklist media rating metadata is available.

```bash
streamlit run migrant_dashboard.py
```

## API Key Options

The app can read an eBird API key from:

- The dashboard password field.
- `EBIRD_API_KEY` in your shell environment.
- `.streamlit/secrets.toml`, copied from `.streamlit/secrets.toml.example`.

Do not commit a real token. Local token files are ignored by git.

## Defaults

The dashboard loads a demo route for Loudoun County, Virginia:

- Region: `US-VA-107`
- Date: `2026-05-02`
- Historical years: `2`
- Minimum sampled checklists per hotspot: `5`

Click `Run optimizer` to fetch live eBird data and solve a fresh route.

## Command Line

```bash
big-day-optimizer \
  --api-key "$EBIRD_API_KEY" \
  --region US-VA-107 \
  --observation-date 2026-05-02 \
  --historical-years 2 \
  --min-checklists-per-hotspot 5 \
  --max-hotspots 40
```

The CLI writes `itinerary.csv` unless another output path is provided.

## How Scoring Works

The optimizer scores expected species across the full trip, not raw checklist length. For each species, repeated chances across stops are combined as:

```text
1 - product(1 - hotspot_probability)
```

This lets multiple modest chances for a species improve the route, while repeated near-certain species add little after the first reliable stop.

## Public Deployment

For public deployments, users should enter their own eBird API key. Set:

```bash
BBD_PUBLIC_DEPLOYMENT=1
```

This prevents the app from reading local token files or `EBIRD_API_KEY`.

Cloud Run deployment:

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
scripts/deploy_cloud_run.sh
```

Deploy the migrant dashboard as a separate Cloud Run service:

```bash
SERVICE_NAME=migrant-hotspots STREAMLIT_APP=migrant_dashboard.py scripts/deploy_cloud_run.sh
```

More deployment notes are in `docs/deploy.md`.

## Development

```bash
python -m unittest discover -s tests
streamlit run dashboard.py
pip install -e .
```

## License

MIT. See `LICENSE`.
