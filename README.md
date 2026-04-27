# Big Day Optimizer

Plan a one-day eBird route that tries to maximize the number of species seen in a selected region. The app combines eBird checklist frequencies, hotspot locations, estimated drive time, dwell-time limits, and species-level probability stacking across stops.

## Use The Dashboard

The dashboard is the intended interface for most users.

```bash
git clone https://github.com/0xJustin/big_big_day.git
cd big_big_day
python -m venv .venv
source .venv/bin/activate
pip install -e .
streamlit run dashboard.py
```

On Windows, activate the environment with:

```powershell
.venv\Scripts\activate
```

If you use `uv`:

```bash
git clone https://github.com/0xJustin/big_big_day.git
cd big_big_day
uv venv
source .venv/bin/activate
uv pip install -e .
streamlit run dashboard.py
```

The dashboard opens in a browser. Enter an eBird API key, choose a region and date, then run the optimizer. The default example is Loudoun County, Virginia (`US-VA-107`) for May 2, 2026.

## eBird API Key

The app can read the key in three ways:

- Paste it into the dashboard field.
- Set `EBIRD_API_KEY` in your shell environment.
- Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and replace the placeholder.

Do not commit a real token. `ebird_token.json` and `.streamlit/secrets.toml` are ignored by git.

## Deploy For Non-Technical Users

The easiest public deployment is Streamlit Community Cloud:

1. Push this repository to GitHub.
2. Create a Streamlit app from `0xJustin/big_big_day`.
3. Set the app file to `dashboard.py`.
4. Add `EBIRD_API_KEY` in Streamlit secrets.
5. Share the Streamlit URL directly, or embed it on a website.

The website in `~/Projects/website` is a static Astro site, so it cannot run this Python optimizer by itself. Use a hosted Streamlit app and add either a normal link or an iframe:

```html
<iframe
  src="https://your-streamlit-app-url"
  style="width: 100%; height: 900px; border: 0;"
  title="Big Day Optimizer"
></iframe>
```

More detail is in `docs/deploy.md`.

## Command Line

After installation, the CLI entrypoint is available as:

```bash
big-day-optimizer \
  --api-key "$EBIRD_API_KEY" \
  --region US-VA-107 \
  --observation-date 2026-05-02 \
  --historical-years 2 \
  --max-hotspots 40
```

It writes a CSV itinerary, defaulting to `itinerary.csv`.

## How The Optimizer Scores Routes

For each hotspot, the app estimates species detection probabilities from matching checklist windows. The route solver uses marginal expected gain, so a species already likely at earlier stops is still valuable at another stop if that second stop materially increases the full-trip probability.

The full-trip species probability is calculated as:

```text
1 - product(1 - hotspot_probability)
```

across the selected stops. This means repeated 20% chances can add up, while repeated near-certain birds add little after the first reliable stop.

## Developer Commands

```bash
python -m unittest discover -s tests
streamlit run dashboard.py
pip install -e .
```

`requirements.txt` is retained for Streamlit-compatible installs. `pyproject.toml` is the package definition used for editable installs and CLI entrypoints.

## License

MIT. See `LICENSE`.
