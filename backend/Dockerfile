FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml ./
RUN uv pip install --system --no-cache -r pyproject.toml || true

COPY app ./app
COPY tests ./tests

RUN uv pip install --system --no-cache fastapi uvicorn[standard] pydantic neo4j numpy scipy \
    opencv-python-headless scikit-learn reportlab pyyaml python-multipart google-generativeai

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
