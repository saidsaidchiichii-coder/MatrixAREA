# MATRIX — Project Mirror : isolated sandbox container
# The AI lives entirely inside this container. The host is never exposed.
FROM python:3.11-slim

# Tools the AI may want inside its world (git, build tools, node for npm).
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl build-essential nodejs npm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY . .

# GEMINI_API_KEY is provided at runtime, never baked into the image:
#   docker run -e GEMINI_API_KEY=xxxx -p 8000:8000 matrix
ENV MATRIX_MODEL=gemini-1.5-flash
EXPOSE 8000

WORKDIR /app/backend
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
