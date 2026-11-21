# NRadio N5000 · OpenWrt

为鲲鹏 NRadio N5000（HC-WT9504）构建的 OpenWrt 固件。基于官方 `mediatek/filogic` Snapshot，使用主线 `mt76` Wi-Fi 驱动和官方 LuCI Bootstrap。OpenWrt 从 TF 卡第二系统分区启动，板载原厂系统可随时切回。

适用于配备 MT7987A、MT7992（BE5040 Wi-Fi 7）、Airoha EN8811H 2.5G LAN/ODU PHY 与内部 2.5G WAN PHY 的 N5000。板级定义从原厂 NROS-2.3.9.n0.c1 设备树逆向校准（见 [docs/hardware-notes.md](docs/hardware-notes.md)）。

## 刷机教程

### 1. 准备固件

- 确认原厂固件为 **NROS-2.3.9 或以上**（本项目在 NROS-2.3.9.n0.c1 上验证第二系统烧录）。
- TF 卡保持在设备内（≥2GB，出厂 8/16GB 均可）。烧录会清除第二系统分区的数据。
- 校验 `sysupgrade.bin` 的 SHA-256 与 `sha256sums` 一致。

### 2. 在原厂系统烧录第二系统

1. 网线连接电脑与 N5000 的 **LAN 口**（EN8811H，机身标注 LAN/ETH1）。原厂管理页 [192.168.88.1](http://192.168.88.1/)，默认密码 `admin`。
2. 进入 **高级设置 → 系统 → Storage Manager**。确认已识别 TF 卡并有 Secondary System Area。
3. 在 **Create Boot Disk** 区域上传 `openwrt-mediatek-filogic-nradio_n5000-squashfs-sysupgrade.bin`，确认擦除第二系统分区。烧录期间保持供电。
4. 烧录成功后，在 **Boot Setting** 选择 **Secondary System First** 并按提示重启。启动失败会自动回退原厂系统。

### 3. 首次进入 OpenWrt

网线保持连接 LAN 口，电脑通过 DHCP 获得 `192.168.1.x` 后访问 [192.168.1.1](http://192.168.1.1/)。

| 项目 | 全新安装默认值 |
| --- | --- |
| OpenWrt 管理地址 | `http://192.168.1.1` |
| LuCI 账号 | `root`，首次登录密码为空 |
| 2.4 GHz Wi-Fi | `NRadio-N5000-2G`，默认开启 |
| 5 GHz Wi-Fi | `NRadio-N5000-5G`，默认开启 |
| 无线密码 | 两个频段均为 `12345678`，WPA2/WPA3 混合加密 |
| 有线端口 | LAN（EN8811H，机身 LAN 丝印口）对应 `eth0`，向客户端分配地址；WAN（内部 2.5G PHY）对应 `eth1`，通过 DHCP 获取上游地址 |

首次登录后在 **系统 → 管理权** 设置管理密码，并在 **网络 → 无线** 修改无线密码。

## 日常使用

| LuCI 菜单 | 用途 |
| --- | --- |
| **系统 → 双系统切换** | 查看下次启动目标（`boot_system`），切回板载原厂系统并重启 |
| **系统 → 在线固件更新** | 检查 GitHub Release，下载校验 SHA-256 后升级 TF 第二系统 |

OpenWrt 的只读根文件系统与可写 `/overlay` 均位于 TF 卡第 4 分区（`/dev/mmcblk0p4`）。板载原厂镜像以只读 `factory-firmware` 分区暴露。启动保护会在分区布局不符时进入 failsafe，防止误用板载配置区作为可写层。

跨内核版本升级请从原厂页面重新烧录完整镜像（同时刷新 TF 上的内核与设备树）；同版本小更新可用 LuCI 在线升级。

## 构建

### 本地（macOS + colima Docker）

```sh
sh build/build-in-docker.sh out
```

脚本自动准备 x86-64 容器、下载官方 Snapshot ImageBuilder、注入板级支持并构建、校验。产物在 `out/`。

### 手动 ImageBuilder（x86-64 Linux）

```sh
curl -fL -o ib.tar.zst \
  https://downloads.openwrt.org/snapshots/targets/mediatek/filogic/openwrt-imagebuilder-mediatek-filogic.Linux-x86_64.tar.zst
mkdir -p ib && tar --use-compress-program=unzstd -xf ib.tar.zst -C ib --strip-components=1
python3 -B board/inject_imagebuilder.py ib
make -C ib image PROFILE=nradio_n5000 FILES=files-n5000 \
  PACKAGES="kmod-usb-net-cdc-ether luci luci-ssl luci-i18n-base-zh-cn luci-i18n-firewall-zh-cn luci-i18n-package-manager-zh-cn iw-full pciutils usbutils picocom"
```

### 完整源码编译

```sh
./scripts/feeds update -a && ./scripts/feeds install -a
python3 -B /path/to/nradio-n5000/board/apply.py .
cp /path/to/nradio-n5000/board/defconfig .config
make defconfig && make -j"$(nproc)"
```

## 仓库目录

| 路径 | 内容 |
| --- | --- |
| [board/](board/) | 设备树、源码与 ImageBuilder 注入脚本、随固件安装的板级文件 |
| [build/](build/) | 本地 Docker 构建脚本 |
| [docs/hardware-notes.md](docs/hardware-notes.md) | 从原厂固件提取的 N5000 硬件档案 |
| [nradio-backup/](nradio-backup/) | 原厂系统调研备份（DTB 反编译、dmesg、分区表、原厂配置） |

本项目结构与板级方案延续 [nradio-c2000-ultra](https://github.com/veildawn/nradio-c2000-ultra)（同平台 MT7987A + MT7992 + TF 双系统）。
