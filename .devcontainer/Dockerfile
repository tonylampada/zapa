FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Set working directory
WORKDIR /workspace

# Copy dependency files
COPY backend/pyproject.toml backend/uv.lock* ./backend/

# Install Python dependencies system-wide
RUN cd backend && uv pip install --system -e ".[dev]"

# Install additional development tools
RUN uv pip install --system ipython pytest-watch psycopg2-binary

# Set Python path
ENV PYTHONPATH=/workspace/backend:$PYTHONPATH

# Keep container running
CMD ["tail", "-f", "/dev/null"]