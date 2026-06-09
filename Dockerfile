FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip python3-venv git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY . .

RUN python3 -m venv /opt/campusops-venv \
    && /opt/campusops-venv/bin/pip install --no-cache-dir -e . \
    && /opt/campusops-venv/bin/pip install --no-cache-dir pytest==8.2.2

ENV PATH="/opt/campusops-venv/bin:${PATH}"
USER root

HEALTHCHECK --interval=5s --timeout=2s --start-period=2s --retries=2 CMD true

CMD ["python3", "-m", "pytest", "-q"]