# water-meter-api/Dockerfile
FROM python:3.10-slim  # Or your chosen Python version

WORKDIR /app

# This is ONE single RUN instruction, with commands chained by &&
# Each line (except the last in the chain) ends with \ for continuation.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        gnupg \
        unixodbc \
        unixodbc-dev \
        lsb-release \
    && \
    curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && \
    curl https://packages.microsoft.com/config/debian/$(lsb_release -rs)/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && \
    apt-get update \
    && \
    ACCEPT_EULA=Y apt-get install -y msodbcsql17 \
    && \
    apt-get clean \
    && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:$PORT", "app:app"]