FROM python:3.12-slim

# System deps required by osmnx's geospatial stack (GDAL/GEOS via
# fiona/shapely wheels usually come pre-built, but curl is useful for
# healthchecks and debugging).
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
