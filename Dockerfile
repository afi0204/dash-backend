# water-meter-api/Dockerfile
FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        gnupg \
        unixodbc \
        unixodbc-dev \
        lsb-release \
    && \
    echo "Attempting to add Microsoft GPG key..." && \
    curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && \
    echo "Attempting to add Microsoft APT repository for Debian release $(lsb_release -rs)..." && \
    # Use lsb_release -rs to get the release number (e.g., 12)
    curl -fsSL https://packages.microsoft.com/config/debian/$(lsb_release -rs)/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && \
    echo "Running apt-get update after adding MS repo..." && \
    apt-get update \
    && \
    echo "Attempting to install msodbcsql17..." && \
    ACCEPT_EULA=Y apt-get install -y msodbcsql17 \
    && \
    echo "Cleaning up apt caches..." && \
    apt-get clean \
    && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:$PORT", "app:app"]