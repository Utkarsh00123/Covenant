# ==========================================
# STAGE 1: Builder (Compiles dependencies)
# ==========================================
FROM python:3.11-slim as builder

# Install uv for blazingly fast dependency resolution
RUN pip install uv

WORKDIR /app
COPY requirements.txt .

# Install dependencies into a virtual environment inside the container
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN uv pip install -r requirements.txt

# ==========================================
# STAGE 2: Runtime (Production Image)
# ==========================================
FROM python:3.11-slim

# Install system dependencies required by our extraction engine (Module 1)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Copy the compiled virtual environment from Stage 1
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Copy the actual application code
COPY ./app ./app

# SECURITY: Create a non-root user to run the application
RUN useradd -m myuser
USER myuser

# Expose the port FastAPI runs on
EXPOSE 8000

# Run FastAPI using Uvicorn
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
