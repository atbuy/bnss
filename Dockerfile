FROM python:3.13-alpine AS python

ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=UTF-8

ENV UV_LINK_MODE=copy
ENV UV_COMPILE_BYTECODE=1

RUN apk --no-cache update && \
  apk --no-cache upgrade


FROM python AS build

# Copy source
COPY . /app
WORKDIR /app

# Install needed binaries and headers
RUN apk add --no-cache gcc musl-dev libffi-dev curl && \
  # Upgrade pip, setuptools and uv
  pip install --no-cache-dir --upgrade pip setuptools uv && \
  # Install dependencies from lock files
  uv sync --no-cache --locked --no-dev --no-editable && \
  # Uninstall unnecessary dependencies
  pip uninstall --no-cache-dir --yes pip setuptools uv


FROM python AS runtime

COPY --from=build /app /app
WORKDIR /app

ENV PATH="/app/.venv/bin:${PATH}"

RUN apk add --no-cache ffmpeg opus

ENTRYPOINT [ "python", "-m", "bnss.main" ]
