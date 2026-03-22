FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (e.g. for PostgreSQL driver asyncpg)
RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files
COPY . .

# Run command is provided dynamically via docker-compose (api or bot)
