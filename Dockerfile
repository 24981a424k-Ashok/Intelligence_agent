# Use a lightweight Python image
FROM python:3.12-slim

# Create a non-root user as recommended by Hugging Face
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

WORKDIR /app

# Install system dependencies (root required temporarily)
USER root
RUN apt-get update && apt-get install -y \
    build-essential \
    libsqlite3-dev \
    git \
    && rm -rf /var/lib/apt/lists/*
USER user

# Copy requirements and install
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Copy the rest of the application
COPY --chown=user . .

# Create data directory for SQLite
RUN mkdir -p /app/data && chmod 777 /app/data

# Set environment variables
ENV PORT=7860
ENV PYTHONUNBUFFERED=1

# Expose the mandatory Hugging Face port
EXPOSE 7860

# Command to start the application (main:app matches our FastAPI instance)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
