# ---- Stage 1: builder ----
FROM python:3.12-slim AS builder
WORKDIR /app
RUN pip install --no-cache-dir build wheel
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt
# ---- Stage 2: runtime ----
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN useradd --create-home appuser
WORKDIR /app
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels
COPY . .
ENV DJANGO_SECRET_KEY=key-for-build
RUN python manage.py collectstatic --noinput
USER appuser
EXPOSE 8000
CMD sh -c "python manage.py migrate && gunicorn config.wsgi:application --bind 0.0.0.0:8000"