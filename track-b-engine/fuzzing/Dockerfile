FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y \
    afl++ cmake gcc clang make \
    libssl-dev build-essential git \
    python3 \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /fuzzing
COPY harness.c .
COPY build.sh .
COPY run_baseline.sh .
COPY summarize_afl.py .
RUN chmod +x build.sh run_baseline.sh && ./build.sh
CMD ["./run_baseline.sh"]
