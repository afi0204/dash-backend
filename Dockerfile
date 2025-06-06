# water-meter-api/Dockerfile

# Use an official Python runtime as a parent image
# Choose a Python version that matches your local development, e.g., 3.10, 3.11, 3.12
# The -slim versions are smaller
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies needed for ODBC and SQL Server Driver
# These instructions are for Debian-based systems (like the one Render often uses)
# For official Microsoft instructions: https://docs.microsoft.com/en-us/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        gnupg \
        unixodbc \
        unixodbc-dev \
        # Add Microsoft GPG key and repository for ODBC driver
        && curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
        && curl https://packages.microsoft.com/config/debian/$(lsb_release -rs)/prod.list > /etc/apt/sources.list.d/mssql-release.list \
        && apt-get update \
        # ACCEPT_EULA=Y is crucial for the msodbcsql17/18 package installation
        && ACCEPT_EULA=Y apt-get install -y msodbcsql17 \
        # If msodbcsql17 gives issues or you prefer the latest, you can try msodbcsql18:
        # && ACCEPT_EULA=Y apt-get install -y msodbcsql18
        # Clean up APT caches to reduce image size
        && apt-get clean \
        && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container at /app
COPY requirements.txt requirements.txt

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app
COPY . .

# Gunicorn will listen on the port specified by Render's $PORT environment variable
# No need to EXPOSE here explicitly as Render handles port mapping.

# Define the command to run your application
# This tells Gunicorn to serve the 'app' instance from your 'app.py' file.
CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:$PORT", "app:app"]