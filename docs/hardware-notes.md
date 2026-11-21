# NRadio N5000 (HC-WT9504) 硬件档案

来源：原厂 NROS-2.3.9.n0.c1 实机提取（LuCI @192.168.88.1，内核 Linux-5.4.281 MTK SDK，
board id `HCMT7987-SNSD`，model `HC-WT9504`， pname `N5000-500`）。备份见 `nradio-backup/`。

## SoC / 内存 / 存储

- MediaTek MT7987A (ARM64 四核 A55) + 1GB DDR
- SPI NOR: Macronix mx25l25645g (32MB)，布局与 C2000 Ultra 相同：
  - BL2 0x0-0x40000 / u-boot-env 0x40000-0x50000 / Factory 0x50000-0x150000
  - bdinfo 0x150000-0x1d0000 / FIP 0x1d0000-0x2d0000 / firmware 0x2d0000-0x2000000
- TF 卡 (mmc0, sd group 4bit 50MHz, broken-cd):
  - p1 4GB 原厂系统区（F2FS overlay, /overlay extroot）
  - p2 1MB / p3 128MB / p4 ~10.4GB = 第二系统区（Storage Manager 显示 second ≈ 10.56GB = p2+p3+p4）

## 以太网（与 C2000 Ultra 的关键差异：LAN/WAN 对调）

- gmac0 (eth0): 2500base-x → Airoha EN8811H @ mdio 0x0b，reset-gpio pio42，reset 10ms/10ms，
  airoha,polarity=1 —— **LAN / ODU 口**，MAC = base MAC
- gmac1 (eth1): internal 2.5G PHY @ mdio 0x0f (c45) —— **WAN 口**，MAC = base+1
- gmac2: HNAT fixed-link（SDK 专用，主线 OpenWrt 忽略）
- 原厂 uci: br-lan = eth0(+eth2), wan = eth1；HNAT wan=eth1

## Wi-Fi

- MT7992 (BE5040, Wi-Fi 7 2.4G EHT40 4x4 + 5G)，PCIe0 @11280000，wifi-reset pio38 (msleep 100)
- 原厂 mtkwifi 闭源驱动；OpenWrt 用 mt76 (kmod-mt7996e + mt7992 固件)
- EEPROM 预期在 Factory 分区 offset 0（与 C2000 相同，待启动验证）
- 原厂 2.4G MAC = base MAC，5G = base+1

## LED / 按键 / 风扇 / PWM

- gpio-leds: status 蓝 pio9 ACTIVE_LOW；error 红 pio12 ACTIVE_LOW（同 C2000）
- 无 cmode/internet LED（C2000 有，N5000 无）
- 按键: reset pio1 ACTIVE_LOW；fandet pio3 ACTIVE_LOW (KEY_CONFIG)
- pwm0 = 蓝色 PWM LED (20kHz, active-low, default-on)
- pwm1 = PWM 风扇 (cooling-levels 0/128/255)；fan-hw 电源 gpio pio5 **ACTIVE_LOW**（C2000 为 HIGH）
- pcie1 disabled（pcie1pereset pio36 hog 输出高）

## 原厂第二系统机制（Storage Manager）

- 上传端点 POST /cgi-bin/luci/nradioadv/system/memory/creat?chunk_offset=..&chunk_size=..&chunk_total=..&chunk_index=..&is_last=..&token=..
  字段 `boot_creat_sd_file`（2MB 分块），完成后轮询 …/burnstatus（status 0=成功）
- 切换: POST …/memory/mode {mode:1} → restart；"Auto-fallback to official system if boot fails"
- 管理口令 admin / root；LAN 默认 192.168.88.1/24
- OTA: POST 192.168.66.1 /api/index.php/Index/upcheck (id=MAC, cur=N5000-<ver>)

## 原厂备份产物（nradio-backup/）

- fw/kernel_mtd.bin (mtd6 原厂 kernel FIT) → fw/factory_board.dts 反编译板级 DTB
- mtd.txt / parts.txt / mounts.txt / cmdline.txt / dmesg.txt / leds*.txt
- cfg/etc/config/*（含 network/fstab/wireless 等）
