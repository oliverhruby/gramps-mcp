# syntax=docker/dockerfile:1

# --- Builder: install build tooling + the project into a standalone prefix ---
# This stage (and everything pip/setuptools/wheel vendor inside it, notably the
# urllib3 copy bundled in pip) is discarded. It exists only to produce /install.
FROM python:3.11-alpine AS builder

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/

RUN pip install --no-cache-dir --upgrade "pip>=26.2.0" "setuptools>=83.0.0" "wheel>=0.46.3" \
    && pip install --no-cache-dir --no-build-isolation --prefix=/install .

# --- Runtime: application + dependencies only, no pip/setuptools/wheel ---
# The runtime image deliberately ships NO pip (which vendors urllib3), so the
# Trivy python-pkg target no longer sees the vendored urllib3. The app needs
# only its installed site-packages and the dist-info metadata (read via
# importlib.metadata in src/gramps_mcp/__init__.py).
FROM python:3.11-alpine

LABEL io.modelcontextprotocol.server.name="io.github.oliverhruby/gramps-mcp"

RUN apk upgrade --no-cache

WORKDIR /app

RUN adduser -D appuser

# Runtime gets only the installed application + dependencies from the builder.
COPY --from=builder /install /usr/local

# The python:* base image bundles pip/setuptools/wheel in /usr/local, and pip
# vendors a copy of urllib3 (the source of the Trivy HIGH findings). Neither is
# needed to run the server, so strip them from the runtime image. The app reads
# its version via importlib.metadata from gramps_mcp_full-*.dist-info, which is
# untouched here.
RUN rm -rf \
    /usr/local/lib/python3.11/site-packages/pip \
    /usr/local/lib/python3.11/site-packages/pip-*.dist-info \
    /usr/local/lib/python3.11/site-packages/setuptools \
    /usr/local/lib/python3.11/site-packages/setuptools-*.dist-info \
    /usr/local/lib/python3.11/site-packages/wheel \
    /usr/local/lib/python3.11/site-packages/wheel-*.dist-info \
    /usr/local/lib/python3.11/site-packages/_distutils_hack \
    /usr/local/lib/python3.11/site-packages/pkg_resources \
    /usr/local/lib/python3.11/site-packages/distutils-precedence.pth \
    /usr/local/lib/python3.11/ensurepip \
    /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.11 \
    /usr/local/bin/wheel

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,socket,sys; t=os.getenv('MCP_TRANSPORT','stdio').lower(); p=int(os.getenv('MCP_PORT','8000')); sys.exit(0) if t=='stdio' else socket.create_connection(('127.0.0.1', p), 2).close()"

USER appuser

ENTRYPOINT ["python", "-m", "gramps_mcp"]
