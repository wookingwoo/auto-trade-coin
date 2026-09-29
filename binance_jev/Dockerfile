FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 JEVBOT_DB_PATH=/data/jevbot.db
WORKDIR /app
COPY pyproject.toml README.md ./
COPY jevbot ./jevbot
RUN pip install --no-cache-dir . && groupadd --gid 10001 trader && useradd --uid 10001 --gid trader --no-create-home trader && mkdir /data && chown trader:trader /data
USER trader
VOLUME ["/data"]
EXPOSE 8765
CMD ["python", "-m", "jevbot", "run"]
