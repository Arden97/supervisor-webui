ARG PROJECT_PATH=/project-of/modules/supervisor-webui

# Build stage
FROM python:3.13.1-slim-bookworm AS builder

# Set environment variables to control Python behavior
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV VIRTUAL_ENV=${PROJECT_PATH}/.venv

RUN pip install uv

RUN mkdir -p ${PROJECT_PATH}/

WORKDIR ${PROJECT_PATH}/

COPY pyproject.toml deploy/docker/uv.lock ${PROJECT_PATH}/

RUN uv venv "$VIRTUAL_ENV" && \
    . "$VIRTUAL_ENV/bin/activate" && \
    uv sync --active --frozen --no-install-project --directory "$VIRTUAL_ENV"

# Final stage
FROM python:3.13.1-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV VIRTUAL_ENV=${PROJECT_PATH}/.venv
ENV PYTHONPATH=${PROJECT_PATH}/
# Set PATH to use the virtual environment
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN mkdir -p ${PROJECT_PATH}/
RUN mkdir -p ${PROJECT_PATH}/{src,frontend,config,certs}

COPY --from=builder $VIRTUAL_ENV $VIRTUAL_ENV
COPY /src ${PROJECT_PATH}/src

WORKDIR ${PROJECT_PATH}/

CMD ["python3", "./src/webserver.py", "--debug"]
