# Use the official lightweight Python image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install build tools, Postgres headers, and netcat
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential \
      gcc \
      libpq-dev \
      netcat-openbsd \
 && rm -rf /var/lib/apt/lists/*

# Copy & install Python dependencies
COPY requirements.docker .
RUN pip install --upgrade pip \
 && pip install --no-cache-dir -r requirements.docker

# Copy your project code
COPY . .

# Make entrypoint executable
RUN chmod +x ./entrypoint.sh

# Expose the port Django will run on
EXPOSE 8000

# Entrypoint will dispatch to web / celery / beat
ENTRYPOINT ["./entrypoint.sh"]