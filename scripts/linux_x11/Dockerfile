# Linux image for `nox -s test-linux-x11` (and compare-drivers' x11-linux configuration): its SDL
# opens real windows on an X server (XQuartz on the Mac host), so the suite runs on Linux with a
# real framebuffer instead of SDL's dummy driver, and plays sound through the Mac's PulseAudio
FROM python:3.14-slim
# X11 client libraries and PulseAudio's client library, which pygame-ce's bundled SDL loads at
# start-up; a C++ compiler for miniaudio, which has no ARM Linux wheel; git for uv's version
# detection
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential git \
        libx11-6 libxext6 libxrender1 libxcursor1 libxi6 libxrandr2 libxss1 libxfixes3 libxkbcommon0 \
        libpulse0 \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir --root-user-action=ignore uv
WORKDIR /work
