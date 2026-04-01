FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY app ./app
COPY docs ./docs

RUN pip install --no-cache-dir .

CMD ["python", "-m", "app.main", "--once"]

