FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    BBD_PUBLIC_DEPLOYMENT=1 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY big_day_optimizer ./big_day_optimizer
COPY dashboard.py migrant_dashboard.py ./

RUN pip install --upgrade pip \
    && pip install .

EXPOSE 8501

CMD streamlit run "${STREAMLIT_APP:-dashboard.py}" --server.port="${PORT:-8501}" --server.address=0.0.0.0
