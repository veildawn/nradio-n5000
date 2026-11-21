#!/usr/bin/env python3
"""Apply the NRadio N5000 board port onto an official OpenWrt main tree."""

import os
import re
import shutil
import sys
from pathlib import Path

from platform_upgrade import patch_platform_upgrade


EXEC_DIRS = {"init.d", "uci-defaults", "sbin", "bin"}


def copy_board_files(files_dir: Path, base_files: Path) -> None:
    if not files_dir.is_dir():
        return
    for src in sorted(files_dir.rglob("*")):
        if src.is_dir():
            continue
        rel = src.relative_to(files_dir)
        dst = base_files / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        if any(part in EXEC_DIRS for part in rel.parts):
            dst.chmod(0o755)
        else:
            dst.chmod(0o644)
    for d in sorted(base_files.rglob("*")):
        if d.is_dir():
            d.chmod(0o755)


def main() -> None:
    os.umask(0o022)
    if len(sys.argv) < 2:
        sys.exit(f"Usage: {sys.argv[0]} <openwrt-dir> [board-dir]")

    root = Path(sys.argv[1]).resolve()
    board_dir = (
        Path(sys.argv[2]).resolve()
        if len(sys.argv) >= 3
        else Path(__file__).resolve().parent
    )

    mk_path = root / "target/linux/mediatek/image/filogic.mk"
    mk_text = mk_path.read_text()
    if "define Device/nradio_n5000\n" in mk_text:
        sys.exit("ERROR: use a clean OpenWrt source tree for this board port.")

    # 1. Copy board DTS
    dts_src = board_dir / "mt7987a-nradio-n5000.dts"
    dts_dst = root / "target/linux/mediatek/dts/mt7987a-nradio-n5000.dts"
    shutil.copyfile(dts_src, dts_dst)

    # 2. Install board files in the Filogic base-files tree.
    base_files = root / "target/linux/mediatek/filogic/base-files"
    copy_board_files(board_dir / "files", base_files)

    # 3. Register Device/nradio_n5000 in filogic.mk
    device_block = """define Device/nradio_n5000
  DEVICE_VENDOR := NRadio
  DEVICE_MODEL := N5000
  DEVICE_DTS := mt7987a-nradio-n5000
  DEVICE_DTS_DIR := ../dts
  SUPPORTED_DEVICES += HCMT7987-SNSD HC-WT9504 NRadio-N5000
  KERNEL_LOADADDR := 0x40080000
  DEVICE_PACKAGES := kmod-usb3 kmod-usb-serial-option kmod-usb-net-cdc-ether \\
\tkmod-usb-net-cdc-ncm kmod-usb-net-huawei-cdc-ncm kmod-usb-net-rndis \\
\tkmod-usb-net-qmi-wwan comgt-ncm uqmi \\
\tkmod-phy-airoha-en8811h airoha-en8811h-firmware \\
\tmt7987-2p5g-phy-firmware kmod-hwmon-pwmfan \\
\tkmod-mt7996e kmod-mt7992-23-firmware kmod-mt7992-firmware \\
\te2fsprogs f2fsck mkf2fs kmod-fs-f2fs kmod-tun uboot-envtools zram-swap
  IMAGE/sysupgrade.bin := sysupgrade-tar | append-metadata
endef
TARGET_DEVICES += nradio_n5000

"""
    anchor = "define Device/nradio_c8-668gl"
    if anchor not in mk_text:
        sys.exit("ERROR: anchor missing in filogic.mk")
    mk_path.write_text(mk_text.replace(anchor, device_block + anchor, 1))

    # 4. Update 02_network (LAN=eth0 EN8811H port, WAN=eth1 internal 2.5G PHY)
    net_path = root / "target/linux/mediatek/filogic/base-files/etc/board.d/02_network"
    net_text = net_path.read_text()

    iface_block = (
        "\tnradio,n5000)\n"
        '\t\tucidef_set_interfaces_lan_wan "eth0" "eth1"\n'
        "\t\t;;\n\n"
    )
    if "\tnradio,n5000)\n" not in net_text:
        if_anchor = "\topenembed,som7981|\\\n\topenwrt,one)\n\t\tucidef_set_interfaces_lan_wan eth1 eth0"
        if if_anchor not in net_text:
            sys.exit("ERROR: eth1/eth0 anchor missing in 02_network")
        net_text = net_text.replace(if_anchor, iface_block + if_anchor, 1)

    mac_block = (
        "\tnradio,n5000)\n"
        "\t\t. /lib/functions/nradio-n5000.sh\n"
        "\t\tlan_mac=$(n5000_get_base_mac)\n"
        '\t\t[ -n "$lan_mac" ] && wan_mac=$(macaddr_add "$lan_mac" 1)\n'
        "\t\tlabel_mac=$lan_mac\n"
        "\t\t;;\n"
    )
    existing_mac_re = re.compile(
        r"\tnradio,n5000\)\n.*?\t\t;;\n(?=\tnradio,c8-668gl\))",
        re.S,
    )
    if existing_mac_re.search(net_text):
        net_text = existing_mac_re.sub(mac_block, net_text, count=1)
    else:
        mac_anchor = "\tnradio,c8-668gl)\n"
        if mac_anchor not in net_text:
            sys.exit("ERROR: mac anchor missing in 02_network")
        net_text = net_text.replace(mac_anchor, mac_block + mac_anchor, 1)
    net_path.write_text(net_text)

    # 4b. Update 11_fix_wifi_mac (override template 00:0c:43:* & multicast EEPROM MACs)
    wifi_mac_path = (
        root
        / "target/linux/mediatek/filogic/base-files/etc/hotplug.d/ieee80211/11_fix_wifi_mac"
    )
    wifi_mac_text = wifi_mac_path.read_text()
    wifi_mac_block = (
        "\tnradio,n5000)\n"
        "\t\t. /lib/functions/nradio-n5000.sh\n"
        '\t\tcur_mac=$(cat /sys${DEVPATH}/macaddress 2>/dev/null)\n'
        '\t\tif ! n5000_mac_is_valid_unicast "$cur_mac"; then\n'
        "\t\t\tbase_mac=$(n5000_get_base_mac)\n"
        '\t\t\tif [ -n "$base_mac" ]; then\n'
        '\t\t\t\t[ "$PHYNBR" = "0" ] && macaddr_add "$base_mac" 2 > /sys${DEVPATH}/macaddress\n'
        '\t\t\t\t[ "$PHYNBR" = "1" ] && macaddr_add "$base_mac" 3 > /sys${DEVPATH}/macaddress\n'
        "\t\t\tfi\n"
        "\t\tfi\n"
        "\t\t;;\n"
    )
    existing_wifi_re = re.compile(
        r"\tnradio,n5000\)\n.*?\t\t;;\n(?=\tnradio,c8-668gl\))",
        re.S,
    )
    if existing_wifi_re.search(wifi_mac_text):
        wifi_mac_text = existing_wifi_re.sub(wifi_mac_block, wifi_mac_text, count=1)
    else:
        wifi_anchor = "\tnradio,c8-668gl)\n"
        if wifi_anchor not in wifi_mac_text:
            sys.exit("ERROR: anchor missing in 11_fix_wifi_mac")
        wifi_mac_text = wifi_mac_text.replace(
            wifi_anchor, wifi_mac_block + wifi_anchor, 1
        )
    wifi_mac_path.write_text(wifi_mac_text)

    # 4c. Register nradio,n5000 in uboot-envtools mediatek_filogic if present
    ubenv_path = root / "package/boot/uboot-envtools/files/mediatek_filogic"
    if ubenv_path.is_file():
        ubenv_text = ubenv_path.read_text()
        if "nradio,n5000" not in ubenv_text and "teltonika,rutc50|\\\n" in ubenv_text:
            ubenv_text = ubenv_text.replace(
                "teltonika,rutc50|\\\n",
                "nradio,n5000|\\\nteltonika,rutc50|\\\n",
                1,
            )
            ubenv_path.write_text(ubenv_text)

    # 5. Install the TF-only upgrade and configuration backup path.
    plat_path = root / "target/linux/mediatek/filogic/base-files/lib/upgrade/platform.sh"
    plat_path.write_text(patch_platform_upgrade(plat_path.read_text()))

    print("Successfully applied NRadio N5000 port to", root)


if __name__ == "__main__":
    main()
