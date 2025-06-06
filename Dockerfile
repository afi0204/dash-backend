# water-meter-api/Dockerfile

# Line 1: Define the base image
FROM python:3.10-slim
# (If you used a different Python version in your minimal successful test, match that here)

# Line 4: Set the working directory in the container
WORKDIR /app

# Line 7: Install basic system dependencies.
# curl is generally useful. Other complex ODBC dependencies are removed.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
    && \
    # Clean up apt caches to reduce image size
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
    # End of the RUN instruction for system packages

# Line 17: Copy the requirements file into the container
COPY requirements.txt requirements.txt

# Line 20: Install Python dependencies from requirements.txt
# This should include Flask, gunicorn, pymongo, python-dotenv, etc.
# Ensure pyodbc is removed or commented out in requirements.txt if not used.
RUN pip install --no-cache-dir -r requirements.txt

# Line 25: Copy the rest of your application code into the container
COPY . .
# This copies app.py, db_mongo_config.py, and any other local modules.

# Line 29: Define the command to run your application using Gunicorn
# Uses the shell form of CMD to allow $PORT environment variable expansion by the shell.
CMD gunicorn --workers 2 --bind "0.0.0.0:$PORT" app:app