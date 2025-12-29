# syntax=docker/dockerfile:1

FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/JacekZubielik/omron-garmin-bridge"
LABEL org.opencontainers.image.description="Bridge between OMRON blood pressure monitors and Garmin Connect + MQTT"
LABEL org.opencontainers.image.licenses="MIT"

# Install system dependencies for Bluetooth
RUN apt-get update && apt-get install -y --no-install-recommends \
    bluez \
    bluetooth \
    libbluetooth-dev \
    libdbus-1-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install PDM
RUN pip install --no-cache-dir pdm

# Copy dependency files and README (required by pyproject.toml)
COPY pyproject.toml pdm.lock README.md ./

# Install dependencies (production only)
RUN pdm install --prod --no-lock --no-editable

# Copy application code
COPY src/ ./src/
COPY streamlit_app/ ./streamlit_app/
COPY config/ ./config/
COPY tools/ ./tools/

# Create data directory
RUN mkdir -p /app/data

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expose Streamlit port
EXPOSE 8501

# Default command - run Streamlit
CMD ["pdm", "run", "streamlit", "run", "streamlit_app/app.py", "--server.address=0.0.0.0", "--server.port=8501"]
