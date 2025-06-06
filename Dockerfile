# water-meter-api/Dockerfile
FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        gnupg \
        apt-transport-https \
        unixodbc \
        unixodbc-dev \
        lsb-release \
    && \
    echo "Downloading Microsoft GPG key..." && \
    curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && \
    chmod go+r /usr/share/keyrings/microsoft-prod.gpg \
    && \
    echo "Adding Microsoft APT repository for Debian release $(lsb_release -rs)..." && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/$(lsb_release -rs)/prod $(lsb_release -cs) main" > /etc/apt/sources.list.d/mssql-release.list \
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