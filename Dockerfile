FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN python -m pip install --upgrade pip && \
    python -m pip install -r requirements.txt

COPY app.py ./app.py
COPY zongce ./zongce
COPY static ./static
COPY deploy/demo_data.sql ./data.sql

RUN mkdir -p /app/data/uploads

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; r=urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8000/', headers={'Accept':'application/json'}), timeout=3); raise SystemExit(0 if r.status == 200 else 1)"

CMD ["python", "app.py"]
