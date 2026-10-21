# Echo Pitch: FastAPI + Microsoft Agent Framework, served on port 8000
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    LLM_MODE=offline ECHO_DATA_DIR=/app/data
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY generator/ generator/
COPY analytics/ analytics/
COPY agents/ agents/
COPY app/ app/
COPY web/ web/
COPY data/ data/
# Regenerate the curated demo matches if the data folder was not shipped
RUN [ -n "$(ls -A data 2>/dev/null)" ] || python -m generator --demo --out data/

RUN useradd -m echo && chown -R echo /app
USER echo
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
