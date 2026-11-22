FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app

# User non-root; /data adalah volume database
RUN useradd --system --uid 10001 app && mkdir /data && chown app:app /data
USER app

EXPOSE 8000
# 1 worker sengaja: hemat memori STB (batas 256 MB)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-server-header"]
