FROM python:3.14.7-slim-bookworm@sha256:82bc3c539b8813ada9d68c63b40158fa002f7f33de9bf3312a3dfdc0620dff56

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 \
    TOKENIZERS_PARALLELISM=false HOME=/tmp IA_RUNTIME=docker

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY docker/ia/requirements.runtime.lock.txt /app/requirements.runtime.lock.txt
RUN python -m pip install --no-cache-dir \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    -r requirements.runtime.lock.txt && python -m pip check
COPY scripts/ia/ /app/scripts/ia/
RUN mkdir -p /app/data/ia/demo_local/revisiones \
    && chown -R 10001:10001 /app/data
USER 10001:10001
EXPOSE 8766
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD ["python", "scripts/ia/docker_salud.py"]
CMD ["python", "scripts/ia/docker_inicio.py"]
