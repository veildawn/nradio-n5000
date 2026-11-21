FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential bash python3 python3-setuptools curl ca-certificates \
      unzip zstd bzip2 xz-utils file rsync git time wget gawk && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /work
