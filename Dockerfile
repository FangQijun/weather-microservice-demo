FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

RUN pip install poetry==2.1.3
COPY pyproject.toml poetry.lock* README.md ./

# Configure poetry to not create a virtual environment, so that the dependencies are installed globally in the container
RUN poetry config virtualenvs.create false
RUN poetry install --no-interaction --no-ansi --no-root

# Copy the rest of the application and run it
COPY . .
CMD ["python", "app/main.py"]