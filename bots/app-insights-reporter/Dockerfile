# Use Amazon ECR to avoid Docker Hub rate limits
FROM public.ecr.aws/docker/library/python:3.11-slim

# Install system dependencies including Node.js for Claude Code and Azure CLI
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    curl \
    ca-certificates \
    nodejs \
    npm \
    gnupg \
    lsb-release \
    && rm -rf /var/lib/apt/lists/*

# Install Azure CLI
RUN curl -sL https://aka.ms/InstallAzureCLIDeb | bash

# Install Claude Code CLI
RUN npm install -g @anthropics/claude-code

# Install Python dependencies
RUN pip install --no-cache-dir \
    slack-sdk \
    requests \
    python-dateutil \
    psycopg2-binary \
    mysql-connector-python

# Set working directory
WORKDIR /app

# Set shell to bash
SHELL ["/bin/bash", "-c"]

CMD ["bash", "/app/run.sh"]
