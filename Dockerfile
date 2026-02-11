FROM python:3.12-slim

WORKDIR /app

# System-Dependencies
RUN apt-get update && apt-get install -y \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 8000

# Start application
CMD ["uvicorn", "backend:app", "--host", "0.0.0.0", "--port", "8000"]
