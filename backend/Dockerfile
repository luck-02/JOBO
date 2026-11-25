FROM python:3.12-slim

# Dépendances système de WeasyPrint + polices standards (rendu ATS)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-lato fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home app
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN mkdir -p data && chown app:app data
USER app

EXPOSE 8000
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
