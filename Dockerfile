FROM python:3.11-alpine

LABEL io.modelcontextprotocol.server.name="io.github.oliverhruby/gramps-mcp"

RUN apk upgrade --no-cache

WORKDIR /app

RUN adduser -D appuser

COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/

RUN pip install --no-cache-dir --upgrade "pip>=26.2.0" "setuptools>=83.0.0" "wheel>=0.46.3" \
    && pip install --no-cache-dir --no-build-isolation .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,socket,sys; t=os.getenv('MCP_TRANSPORT','stdio').lower(); p=int(os.getenv('MCP_PORT','8000')); sys.exit(0) if t=='stdio' else socket.create_connection(('127.0.0.1', p), 2).close()"

USER appuser

ENTRYPOINT ["python", "-m", "gramps_mcp"]
