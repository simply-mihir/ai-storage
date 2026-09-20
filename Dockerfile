FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir ".[prod]"

COPY static/ static/
COPY data/synthetic/ data/synthetic/
COPY configs/ configs/

EXPOSE 8001

CMD ["uvicorn", "storage_advisor.app.api:app", "--host", "0.0.0.0", "--port", "8001"]
