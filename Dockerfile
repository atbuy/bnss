FROM python:3.10-alpine3.17 as python

# Python cofiguration
ENV PYTHONBUFFERED=true


# Install dependencies in the build stage
FROM python as build

# Copy source
COPY . /app
WORKDIR /app

# Poetry configuration
ENV POETRY_HOME=/opt/poetry
ENV POETRY_VIRTUALENVS_IN_PROJECT=true
ENV PATH="$POETRY_HOME/bin:${PATH}"

# Install needed binaries and headers
RUN apk add --no-cache gcc musl-dev libffi-dev curl && \
    # Upgrade pip and setuptools
    pip install --upgrade pip setuptools wheel && \
    # Install poetry
    curl -sSL https://install.python-poetry.org | python3 - || cat /app/poetry*.log && \
    # Install dependencies from poetry lock file
    poetry install --no-dev --no-interaction --no-ansi -vvv


# Run app in runtime stage
FROM python as runtime

RUN apk add --no-cache ffmpeg opus

# Add poetry virtual environment to PATH
ENV PATH="/app/.venv/bin:${PATH}"

# Copy source
COPY --from=build /app /app
WORKDIR /app

CMD [ "python", "-m", "bnss.main" ]
