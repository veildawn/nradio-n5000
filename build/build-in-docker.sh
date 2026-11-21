#!/bin/sh
# Build the NRadio N5000 OpenWrt firmware inside an x86-64 container.
# Usage: sh build/build-in-docker.sh [output-dir]
set -eu

PROJ="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$PROJ/out}"
IBDIR="/tmp/ib"
IMAGE="openwrt/ibuilder:local"

mkdir -p "$OUT"

# One-time: build the ImageBuilder container image (Debian bookworm + deps).
docker build -t "$IMAGE" - "$PROJ/build" <<'DOCKERFILE'
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential bash python3 python3-setuptools curl ca-certificates \
      unzip zstd bzip2 xz-utils file rsync git subversion time wget \
      libncurses-dev gawk gettext swig && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /work
DOCKERFILE

# Download + extract the official mediatek/filogic ImageBuilder once.
if [ ! -d "$IBDIR/extracted" ] || [ ! -x "$IBDIR/extracted/Makefile" ]; then
  mkdir -p "$IBDIR/extracted"
  curl -fL --retry 3 -o "$IBDIR/ib.tar.zst" \
    https://downloads.openwrt.org/snapshots/targets/mediatek/filogic/openwrt-imagebuilder-mediatek-filogic.Linux-x86_64.tar.zst
  tar --use-compress-program=unzstd -xf "$IBDIR/ib.tar.zst" -C "$IBDIR/extracted" --strip-components=1
  rm -f "$IBDIR/ib.tar.zst"
fi

docker run --rm --platform linux/amd64 \
  -v "$PROJ":/src -v "$IBDIR/extracted":/tmp/ib -v "$OUT":/out \
  -e HOME=/tmp -w /tmp/ib "$IMAGE" bash -eux -c '
    python3 -B /src/board/inject_imagebuilder.py /tmp/ib

    umask 022
    make -C /tmp/ib image \
      PROFILE="nradio_n5000" \
      PACKAGES="kmod-usb-net-cdc-ether luci luci-ssl luci-i18n-base-zh-cn luci-i18n-firewall-zh-cn luci-i18n-package-manager-zh-cn iw-full pciutils usbutils picocom" \
      FILES="files-n5000"

    BIN=/tmp/ib/bin/targets/mediatek/filogic/openwrt-mediatek-filogic-nradio_n5000-squashfs-sysupgrade.bin
    DTB=$(echo /tmp/ib/build_dir/target-*/linux-mediatek_filogic/image-mt7987a-nradio-n5000.dtb)
    FACTORY_PART=/soc/spi@11009800/flash@0/partitions/partition@2d0000
    test -f "$BIN"
    test "$(fdtget "$DTB" "$FACTORY_PART" label)" = factory-firmware
    fdtget "$DTB" "$FACTORY_PART" read-only
    /tmp/ib/staging_dir/host/bin/fwtool -i /tmp/meta.json "$BIN"
    python3 - <<PY
import json, struct, tarfile
meta = json.load(open("/tmp/meta.json"))
assert meta["compat_version"] == "1.0", meta
expected = {"nradio,n5000", "HCMT7987-SNSD", "HC-WT9504", "NRadio-N5000"}
assert expected == set(meta["supported_devices"]), meta["supported_devices"]
with tarfile.open("$BIN") as tf:
    names = tf.getnames()
    assert any(n.endswith("/CONTROL") for n in names)
    assert any(n.endswith("/kernel") for n in names)
    assert any(n.endswith("/root") for n in names), names
    root = tf.getmember("sysupgrade-nradio_n5000/root")
    header = tf.extractfile(root).read(48)
    assert header[:4] == b"hsqs", "TF rootdisk requires SquashFS"
    bytes_used = struct.unpack_from("<Q", header, 40)[0]
    assert 0 < bytes_used <= root.size
    assert (bytes_used + 65535) // 65536 == (root.size + 65535) // 65536
print("metadata checks passed")
PY
    cp -f /tmp/ib/bin/targets/mediatek/filogic/openwrt-mediatek-filogic-nradio_n5000* /out/
    cp -f /tmp/ib/bin/targets/mediatek/filogic/profiles.json /out/ || true
    cp -f "$DTB" /out/image-mt7987a-nradio-n5000.dtb
    (cd /out && sha256sum openwrt-mediatek-filogic-nradio_n5000-squashfs-sysupgrade.bin > sha256sums)
    echo "BUILD OK -> $OUT"
  '
