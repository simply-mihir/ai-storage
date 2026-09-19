FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir ".[prod]"

COPY app/ app/
COPY data/synthetic/ data/synthetic/
COPY data/processed/ data/processed/
COPY configs/ configs/

EXPOSE 8501 8000

COPY scripts/entrypoint.sh .
RUN chmod +x entrypoint.sh
CMD ["./entrypoint.sh"]
