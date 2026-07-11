FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# Runtime libraries for OpenCV, Playwright/Chromium, EasyOCR, and Tk/web helpers used by chart workflows.
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

RUN python -m pip install --upgrade pip setuptools wheel

COPY pyproject.toml poetry.lock ./
# The Poetry lock currently resolves EasyOCR through GPU-enabled PyTorch/CUDA wheels.
# Installing Docker runtime dependencies directly avoids downloading those multi-GB
# NVIDIA packages and then installs CPU-only PyTorch before EasyOCR.
RUN pip install \
        "colorama>=0.4.6,<0.5.0" \
        "dash>=4.1.0,<5.0.0" \
        "flask>=3.1.1,<4.0.0" \
        "numpy>=2.2.6,<3.0" \
        "pandas>=2.3.3,<4.0" \
        "plotly>=6.0.1,<7.0.0" \
        "tabulate>=0.9.0,<0.11.0" \
        "tenacity>=9.1.2,<10.0.0" \
        "playwright>=1.55.0,<2.0.0" \
        "yfinance>=1.3.0,<2.0.0" \
        "opencv-python>=4.13.0.92,<5.0.0" \
    && pip install --index-url https://download.pytorch.org/whl/cpu \
        "torch==2.7.1" \
        "torchvision==0.22.1" \
    && pip install \
        "Pillow>=12.0.0,<13.0.0" \
        "scipy>=1.16.0" \
        "scikit-image>=0.25.0" \
        "python-bidi>=0.6.0" \
        "PyYAML>=6.0.0" \
        "Shapely>=2.0.0" \
        "pyclipper>=1.3.0" \
        "ninja>=1.11.0" \
    && pip install --no-deps "easyocr==1.7.2" \
    && pip freeze | awk -F== '/^nvidia-/ {print $1}' | xargs -r pip uninstall -y \
    && rm -rf /root/.cache/pip
RUN python -m playwright install chromium \
    && chmod -R a+rX /ms-playwright \
    && apt-get purge -y --auto-remove build-essential curl \
    && rm -rf /var/lib/apt/lists/* /tmp/*

COPY . .
RUN chmod +x /app/run /app/refresh

ENTRYPOINT ["python", "run"]
CMD ["--help"]
