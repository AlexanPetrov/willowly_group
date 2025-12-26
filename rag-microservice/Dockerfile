FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1

WORKDIR /app

# Install uv for fast dependency installation
RUN pip install --no-cache-dir uv

# Copy pyproject.toml and lock file
COPY pyproject.toml uv.lock /app/

# Install dependencies (app + dev group) into system environment (no venv inside image)
RUN uv pip install --system --no-cache-dir -e . --group dev

COPY . /app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
