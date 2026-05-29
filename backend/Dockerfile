# Multi-stage Build for FastAPI Backend
FROM python:3.11-slim as builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install dependencies into user space
RUN pip install --no-cache-dir --user -r requirements.txt

# Final Runner Image
FROM python:3.11-slim as runner

WORKDIR /app

# Copy installed python dependencies from builder
COPY --from=builder /root/.local /root/.local
COPY . .

# Update PATH env to access user-installed binaries (like uvicorn)
ENV PATH=/root/.local/bin:$PATH
ENV PORT=8000
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
