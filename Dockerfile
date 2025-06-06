# water-meter-api/Dockerfile
FROM python:3.10-slim # Or your preferred Python version

WORKDIR /app

# Install basic dependencies. ODBC drivers no longer needed.
# curl might still be useful for general purposes or future needs.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
    && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Use the shell form of CMD to allow $PORT environment variable expansion
CMD gunicorn --workers 2 --bind "0.0.0.0:$PORT" app:app