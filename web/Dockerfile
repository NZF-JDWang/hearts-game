FROM python:3.12-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir fastapi uvicorn websockets

# Copy backend code
COPY backend/engine.py /app/
COPY backend/ai.py /app/
COPY backend/main.py /app/
COPY backend/session.py /app/
COPY backend/roster.py /app/

# Copy frontend static files (including avatars)
COPY backend/static /app/static

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
