FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN groupadd --gid 10001 dashboard && useradd --uid 10001 --gid dashboard --no-create-home dashboard \
    && mkdir /app/data && chown dashboard:dashboard /app/data
COPY --chown=dashboard:dashboard usage_dashboard/ ./usage_dashboard/
COPY --chown=dashboard:dashboard examples/config.demo.json ./examples/config.demo.json
COPY LICENSE ./LICENSE
USER dashboard
EXPOSE 8900
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8900/healthz', timeout=3)"
CMD ["python", "-m", "usage_dashboard", "--host", "0.0.0.0", "--config", "examples/config.demo.json"]
