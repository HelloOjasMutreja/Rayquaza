# Dockerfile -- Rayquaza reproducibility wizard runner image.
# Bundles the build toolchain, liboqs, and the compiled Track A target
# binaries. Does NOT bundle any Ollama model weights -- those are pulled at
# runtime by the wizard based on detected hardware (see bootstrap/hardware.py).
FROM python:3.11-slim

ENV HOME=/root

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    ninja-build \
    git \
    libssl-dev \
    bash \
    && rm -rf /var/lib/apt/lists/*

# Build liboqs. No version pin is recorded anywhere in this repo (checked:
# EXPERIMENT_LOG.md and track-a-target/TRACK_A_PLAN.md), so this clones the
# default branch at build time and records the resolved commit, rather than
# guessing a tag that may not exist. The source tree under /root/liboqs/src
# is kept (not deleted) because kyber512_leak5/setup.sh copies reference
# files from it; only the build/ subdirectory is dropped after install.
RUN git clone --depth 1 https://github.com/open-quantum-safe/liboqs.git /root/liboqs \
    && mkdir -p /build-info \
    && git -C /root/liboqs rev-parse HEAD > /build-info/liboqs-commit.txt \
    && cmake -S /root/liboqs -B /root/liboqs/build -GNinja \
         -DCMAKE_INSTALL_PREFIX=/root/liboqs-install \
         -DCMAKE_BUILD_TYPE=Release \
    && cmake --build /root/liboqs/build \
    && cmake --install /root/liboqs/build \
    && rm -rf /root/liboqs/build

WORKDIR /app
COPY track-a-target/ /app/track-a-target/
COPY track-b-engine/ /app/track-b-engine/
COPY shared/ /app/shared/
COPY bootstrap/ /app/bootstrap/
COPY run_bootstrap.py requirements-bootstrap.txt requirements-sandbox.txt /app/

RUN pip install --no-cache-dir -r requirements-bootstrap.txt -r requirements-sandbox.txt

# Build every target directory: run its setup.sh first if it has one (only
# kyber512_leak5 does, to copy reference files from the liboqs source tree
# above), then make. mldsa44_leak1 is built too even though the wizard
# doesn't run it automatically, so the manual path in
# docs/reproducing-mldsa.md works without extra setup.
RUN for dir in track-a-target/targets/*/; do \
        if [ -f "$dir/setup.sh" ]; then \
            (cd "$dir" && bash setup.sh); \
        fi; \
        (cd "$dir" && make); \
    done

ENV RAYQ_OLLAMA_URL=http://ollama:11434/api/chat
ENV RAYQ_OLLAMA_BASE=http://ollama:11434

CMD ["python", "run_bootstrap.py"]
