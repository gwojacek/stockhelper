FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_VERSION=1.8.5 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    PIP_NO_CACHE_DIR=1 \
    POETRY_CACHE_DIR=/tmp/poetry-cache

WORKDIR /app

# Runtime libraries for OpenCV, Playwright/Chromium, and Tk/web helpers used by chart workflows.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        libgtk-3-0 \
        libnss3 \
        libx11-xcb1 \
        libxcb-dri3-0 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxrandr2 \
        libasound2 \
        libatk-bridge2.0-0 \
        libatk1.0-0 \
        libcups2 \
        libdrm2 \
        libgbm1 \
        libpango-1.0-0 \
        libcairo2 \
        libxkbcommon0 \
        xdg-utils \
    && rm -rf /var/lib/apt/lists/*

RUN pip install "poetry==$POETRY_VERSION"

COPY pyproject.toml poetry.lock ./
# EasyOCR pulls GPU-enabled PyTorch/CUDA wheels from the lockfile by default.
# Replace that stack with CPU-only PyTorch so Stooq CAPTCHA OCR works without a multi-GB CUDA image.
RUN poetry install --only main --no-root --no-ansi \
    && pip uninstall -y easyocr torch torchvision triton \
    && pip freeze | awk -F== '/^nvidia-/ {print $1}' | xargs -r pip uninstall -y \
    && pip install --index-url https://download.pytorch.org/whl/cpu "torch==2.7.1" "torchvision==0.22.1" \
    && pip install --no-deps "easyocr==1.7.2" \
    && rm -rf "$POETRY_CACHE_DIR" /root/.cache/pip /root/.cache/pypoetry
RUN python -m playwright install chromium \
    && apt-get purge -y --auto-remove build-essential curl \
    && rm -rf /var/lib/apt/lists/* /tmp/*

COPY . .
RUN chmod +x /app/run /app/refresh

ENTRYPOINT ["python", "run"]
CMD ["--help"]
