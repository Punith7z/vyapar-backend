FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose the port (Render sets PORT env variable)
ENV PORT=8000
EXPOSE $PORT

# Start the FastAPI application
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port $PORT"]
