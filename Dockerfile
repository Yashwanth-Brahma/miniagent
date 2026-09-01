# start from a slim official Python image
FROM python:3.12-slim

# install uv (your package manager) into the image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ ./src/
COPY quorra_docs.md ./
RUN uv sync --frozen --no-dev

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "miniagent.server:app", "--host", "0.0.0.0", "--port", "8000"]