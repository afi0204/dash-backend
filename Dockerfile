# water-meter-api/Dockerfile

# Line 1: Define the base image
FROM python:3.10-slim
# If you prefer a different Python version, change it here, e.g., python:3.12-slim

# Line 4: Set the working directory in the container
WORKDIR /app

# Line 7: Install system dependencies including lsb-release for ODBC setup
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
    echo "Attempting to add Microsoft GPG key..." && \
    curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && \
    echo "Attempting to add Microsoft APT repository for Debian $(lsb_release -cs)..." && \
    # Use lsb_release -cs to get the codename (e.g., bookworm)
    curl -fsSL https://packages.microsoft.com/config/debian/$(lsb_release -cs)/prod.list > /etc/apt/sources.list.d/mssql-release.list \
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
    # End of the long RUN instruction

# Line 34: Copy the requirements file into the container
COPY requirements.txt requirements.txt

# Line 37: Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Line 40: Copy the rest of the application code into the container
COPY . .

# Line 43: Define the command to run your application using Gunicorn
CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:$PORT", "app:app"]