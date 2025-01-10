from ghcr.io/astral-sh/uv:debian-slim
ADD  . ./app
WORKDIR /app
RUN uv sync --frozen
CMD ["uv", "run", "fastapi","run", "--workers", "4", "main.py"]