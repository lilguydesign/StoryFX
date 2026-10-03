FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 STORYFX_STATE_DIR=/data
WORKDIR /app
COPY server/requirements-lock.txt /app/server/requirements-lock.txt
RUN pip install --no-cache-dir -r /app/server/requirements-lock.txt \
    && useradd --uid 10000 --no-create-home storyfx
COPY server/storyfx_server /app/server/storyfx_server
COPY dashboard /app/dashboard
USER 10000:10000
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "storyfx_server.main:app_factory", "--factory", "--app-dir", "/app/server", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
