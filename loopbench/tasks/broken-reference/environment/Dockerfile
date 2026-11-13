FROM python:3.12-slim
RUN pip install --no-cache-dir pytest==8.3.3 \
    && useradd --create-home --shell /bin/sh agent
WORKDIR /workspace
RUN chown agent:agent /workspace
