# KeeneticOS cho Viettel vAP-32X6V1

Chạy KeeneticOS (bản KN-3812 Hopper SE) **độc lập** trên 32x6: dual image như máy Keenetic thật, NMBM, có phân vùng
Storage, U-Boot dual image lấy từ bản port NR3053. Không còn OpenWrt hay Multi Firmware trên máy. Bản chạy song song
với OpenWrt nằm ở nhánh `5.1.8-multifw`.

Repo gồm bản vá và script. Phần mềm đóng của Keenetic (ndm, web UI, driver) được lấy lúc build từ ảnh KN-3812
chính hãng đặt trong `stock/`. Bootloader là patch trong `bootloader/`, áp lên `bl-mt798x-dhcpd`.

## Layout NAND (128 MiB, NMBM)

NMBM quản lý 120 MiB đầu (`nmbm0`, 0x7800000); 8 MiB cuối là vùng NMBM dùng cho bảng ánh xạ và khối thay thế.

| Địa chỉ (nmbm0) | Phân vùng | Kích thước |
|---|---|---|
| 0x0000000 | BL2 (gốc Viettel, không đổi) | 1 MiB |
| 0x0100000 | U-Config (danh tính Keenetic) | 512 KiB |
| 0x0180000 | Factory (MAC + calibration Wi-Fi, không bao giờ ghi) | 2 MiB |
| 0x0380000 | FIP (BL31 + U-Boot dual image) | 2 MiB |
| 0x0580000 | u-boot-env | 512 KiB |
| 0x0600000 | RF-EEPROM (bản sao Factory 0x0–0xa0000, MAC LAN ở 0x4, WAN ở 0xa) | 1 MiB |
| 0x0700000 | Firmware_1 | 32 MiB |
| 0x2700000 | Config_1 | 512 KiB |
| 0x2780000 | Dump | 512 KiB |
| 0x2800000 | Storage_A | 20 MiB |
| 0x3c00000 | U-State | 512 KiB |
| 0x3c80000 | (dự trữ) | 2 MiB |
| 0x3e80000 | D-State | 512 KiB |
| 0x3f00000 | RF-EEPROM_res | 1 MiB |
| 0x4000000 | Firmware_2 | 35 MiB |
| 0x6300000 | Config_2 | 512 KiB |
| 0x6380000 | Storage_B | 20,5 MiB |

ndm ghép Storage_A và Storage_B thành một ổ UBIFS khoảng 40 MiB. U-Boot đọc U-State để chọn ảnh, boot thử ảnh mới
và quay về ảnh cũ nếu ảnh mới không chạy.

## Những gì được sửa

| File | Tác dụng |
|---|---|
| `kernel/402-ndmpart-viettel-32x6-layout.patch` | ndmpart: BL2, U-Config, FIP, RF-EEPROM và Firmware_1 theo layout 32x6 trên NMBM |
| `kernel/406-ndmpart-di-viettel-32x6.patch` | Chưa có U-State (máy mới cài) thì dùng mặc định trong RAM: ảnh 1 chạy, ảnh 2 dự phòng |
| `kernel/408-spinand-w25n01kv-oob64-viettel-32x6.patch` | W25N01KV báo 64 byte OOB như BL2 gốc (xem dưới) |
| `kernel/KN-3812.dts` | RAM 256 MiB, NMBM (không `forced-create`), không USB, `/chosen/dualimage`, pull-up cho nút RESET/WPS, giữ GPIO 39 (reset MT7531) mức cao, tắt LED đỏ/xanh dương và hai chân phụ của LED xanh lá |
| `kernel/config-4.9.additions` | pstore; `apply-to-sdk.sh` đặt `CONFIG_MTD_NDM_FLASH_SIZE_LIMIT=0x2800000` |
| `binpatch/phr_32x6_patch.py` | `phr.ko`: nút RESET GPIO 1, nút WLAN (WPS) GPIO 0; LED trạng thái KN-3812 (xanh/cam) → xanh lá GPIO 8 / đỏ GPIO 5; không USB; GPIO 39 mức cao |
| `binpatch/ndw4_no_ndns_getbooked_patch.py` | Web UI: chỉ hỏi KeenDNS "get-booked" ở chế độ router (lấy từ bản NR3053) |
| `rootfs/ndm_default_config_32x6.py` | Cấu hình mặc định: ISP = GigabitEthernet0/0 (jack WAN, VLAN 2), GigabitEthernet1 + 1/0 (PHY SoC, không có jack) tắt, **tắt auto-update** |
| `rootfs/webui_32x6.py` | Web UI và wizard theo phần cứng 32x6: 3 cổng, wizard lấy jack WAN làm cổng Internet, model `vAP-32X6V1` |
| `bootloader/bl-mt798x-keenetic-32x6.patch` | U-Boot dual image cho 32x6 (xem *Build → Bootloader*) |
| `tools/mk_keenetic_data.py` | Tạo `uconfig.bin` (danh tính sinh cố định từ Factory, Wi-Fi mặc định `Keenetic` / `12345678`) và `rf-eeprom.bin` từ bản dump Factory |
| `stock/` | Ảnh KN-3812 chính hãng (`.bin`, không commit), danh sách thành phần của nó (`.txt`) và sha256 |
| `debug/` | Overlay rootfs cho bản build gỡ lỗi (`DEBUG=1`) |

**OOB 64 byte.** BL2 gốc đọc kích thước OOB của W25N01KV từ parameter page (64), U-Boot của OpenWrt cũng dùng 64,
nhưng U-Boot 2025.07 và kernel 4.9 khai 96. NMBM ghi kích thước này vào signature và từ chối signature khác: U-Boot
96 tạo lại NMBM, rồi BL2 gốc báo `NMBM configuration mismatch` và dừng. U-Boot (`winbond.c`) và kernel (patch 408)
đều dùng 64; byte 64–95 là ECC trong chip, không dùng được.

**Pull-up nút.** 32x6 không có điện trở kéo lên ngoài cho GPIO 0/1. Không có pull-up trong chip, `phr.ko` đọc RESET
là đang giữ lúc khởi động và ndm reset cấu hình rồi khởi động lại mỗi lần boot (NR3053 bị y hệt ở GPIO 24).

Auto-update phải tắt và **không bao giờ nạp ảnh KN-3812 chính hãng lên máy**: layout và DTS khác 32x6, và ảnh đó
dùng NMBM `forced-create`.

## Ảnh chính hãng (`stock/`)

`KN-3812_stable_5.1.8_5.01.C.8.0-2.bin` là firmware Keenetic Hopper SE (KN-3812) bản 5.1.8 stable, mã build
5.01.C.8.0-2. File `.txt` cùng tên là danh sách thành phần của ảnh đó, cùng định dạng dòng `components` của
`show version`. Lúc build, danh sách này được đưa nguyên vẹn cho `configure.sh -p manual KN-3812` của SDK. Không bỏ
thành phần nào (kể cả USB/lưu trữ): bỏ chúng làm thay đổi bộ driver mạng nạp lúc khởi động, và `hw_nat.ko` sẽ panic
trong `ppe_init`, khiến máy khởi động lại liên tục.

Ảnh `.bin` là phần mềm đóng của Keenetic nên không commit vào git (`.gitignore`). Clone mới thì tải đúng bản
5.01.C.8.0-2 của KN-3812 từ Keenetic, đặt vào `stock/`, rồi kiểm tra:

```bash
cd keenetic-32x6/stock
curl -fLO https://osvault.keenetic.ru/KN-3812/5.01/KN-3812_stable_5.1.8_5.01.C.8.0-2.bin
sha256sum -c sha256sums
```

### Build trên GitHub

Actions → **Build KeeneticOS for Viettel 32x6** → Run workflow, chọn nhánh. Workflow tải ảnh gốc ở trên, build
KeeneticOS và (nhánh này) FIP + BL2 chạy RAM, rồi tạo release tag `5.01.C.8.0-2` (mã build của KeeneticOS) chỉ chứa
**bootloader**. Build lại cùng phiên bản thì release cũ bị thay.

**Ảnh KeeneticOS không được đăng** (dòng chép nó vào release để comment trong workflow): ảnh chứa phần đóng của
Keenetic lấy từ ảnh gốc (`ndm`, `ndw4`, web UI, module build sẵn, `phr.ko` đã vá). Chúng không theo GPL và Keenetic
không cho phép phát tán lại, nên ảnh chỉ dùng cho router của chính mình: tự build bằng `scripts/build-wsl.sh`. Trên
Actions, bước build KeeneticOS chỉ để kiểm tra là build được. `uconfig.bin` và `rf-eeprom.bin` cũng không có trong
release vì mỗi router một khác.

## Build

### KeeneticOS

Cần WSL/Linux như hướng dẫn của SDK (thêm `xxd kmod bison flex`) và SDK cùng phiên bản:

```bash
git clone --depth 1 -b 5.01.C.8.0-2 https://github.com/keenetic/keenetic-sdk.git ~/keenetic-sdk
```

```bash
bash keenetic-32x6/scripts/build-wsl.sh
```

Script chép repo sang `~/kn-32x6-port`, chạy `scripts/apply-to-sdk.sh`, rồi `make`. Bước apply gồm: vá kernel, DTS,
config, `unpack.sh` ảnh trong `stock/`, chọn thành phần, vá `phr.ko`, sửa default-config và web UI. Khi `kernel/`
thay đổi (kể cả khi đổi nhánh), script tự `make target/linux/clean`. Ảnh ra ở `~/keenetic-sdk/bin/mt7981/*KN-3812*.bin`.

**Bản gỡ lỗi** (`DEBUG=1 bash keenetic-32x6/scripts/build-wsl.sh`): init chạy `/etc/dbg.sh` thay cho ndm, chạy ndm
dưới strace và chép log của ndm vào log kernel. `/bin/sh` của KeeneticOS là "NDM Shell Wrapper" chạy script bằng
`/opt/bin/sh`, nên bản gỡ lỗi đặt một busybox có `sh` ở đó.

### Bootloader

`bootloader/bl-mt798x-keenetic-32x6.patch` áp lên `bl-mt798x-dhcpd` nhánh `keenetic-nr3053-mod` (commit
`4bb66a637`). Patch gồm: U-Boot dual image của NR3053 (U-Config/ndm env, chọn ảnh theo U-State, failsafe ghi ảnh
không chạy), layout 32x6 (`CONFIG_MTK_KEENETIC_DI_LAYOUT_32X6`), board `keenetic_32x6` với DTS
`mt7981-viettel-32x6`, W25N01KV OOB 64. Clone trên Linux/WSL (trên Windows checkout lỗi vì một tên file kết thúc
bằng dấu cách):

```bash
git clone -b keenetic-nr3053-mod https://github.com/thanhnhu/bl-mt798x-dhcpd.git && cd bl-mt798x-dhcpd
git checkout 4bb66a637 && git apply ../keenetic-32x6/bootloader/bl-mt798x-keenetic-32x6.patch
BOARD=keenetic_32x6 SOC=mt7981 VERSION=SP1 VARIANT=default COPY_BL2=0 ./build.sh
```

Ra `output/fip-mt7981_keenetic_32x6_SP1-*.bin`. BL2 giữ bản gốc Viettel, không build. BL2 chạy RAM để cứu máy qua UART
(`bl2-32x6-ram.bin`) build từ cùng ATF với `_BOOT_DEVICE_RAM=y` và `_RAM_BOOT_RAM_BOOT_UART_DL=y`.

## Cài

| File | Lấy ở đâu | Là gì, dùng thế nào |
|---|---|---|
| `KeeneticOS-32x6-5.01.C.8.0-2.bin` | Tự build (*Build*, đổi tên ảnh `*KN-3812*.bin`) | Firmware KeeneticOS. Cài: ghi vào Firmware_1 (*Cài từ OpenWrt*). Nâng cấp: web failsafe |
| `fip-keenetic-32x6.bin` | Release `5.01.C.8.0-2` | BL31 + U-Boot dual image. Ghi vào `fip` **một lần** khi cài; nâng cấp KeeneticOS không cần ghi lại |
| `bl2-32x6-ram.bin` | Release `5.01.C.8.0-2` | BL2 chạy trong RAM. **Không bao giờ ghi vào flash**, chỉ để cứu máy qua UART |
| `uconfig.bin`, `rf-eeprom.bin` | Tự tạo từ Factory của chính máy | Định danh KeeneticOS và Wi-Fi EEPROM/MAC. Ghi một lần khi cài |
| `sha256sums` | Release | Kiểm file tải về: `sha256sum -c sha256sums` |

Tạo `uconfig.bin` và `rf-eeprom.bin` (mỗi máy một bộ, không dùng lại của máy khác):

```bash
python3 keenetic-32x6/tools/mk_keenetic_data.py factory.bin kn-data
```

| Máy đang chạy | Làm gì |
|---|---|
| Firmware Viettel gốc | Backup, cài OpenWrt theo mục 4 của `OpenWRT/README-viettel-32x6.md`, rồi *Cài từ OpenWrt* |
| OpenWrt/ImmortalWrt (có hay không Multi Firmware) | *Cài từ OpenWrt*. **Mọi firmware và dữ liệu trong UBI bị xoá** |
| KeeneticOS độc lập này | Nâng cấp qua web failsafe (bên dưới); cấu hình giữ nguyên |
| Ảnh KN-3812 chính hãng | **Không bao giờ** (xem trên) |

### Cài từ OpenWrt

1. Dump Factory về PC (`ssh root@192.168.1.1 'cat /dev/mtd2ro' > factory.bin`), tạo `uconfig.bin` và `rf-eeprom.bin`.
2. Chạy OpenWrt từ RAM (recovery initramfs), để NAND không còn ai dùng. Với OpenWrt 25.12 Multi Firmware:
   `ubirename fit fit_off` rồi khởi động lại, U-Boot sẽ vào recovery.
3. Chép các file lên `/tmp` (`scp -O`), xem tên phân vùng bằng `cat /proc/mtd`, rồi ghi theo địa chỉ `nmbm0` ở trên.
   Với OpenWrt 25.12 (`ubi` bắt đầu ở 0x580000, `u-boot-env` ở 0x100000):

   ```bash
   insmod mtd-rw i_want_a_brick=1
   mtd erase ubi
   mtd -p 0x80000 write /tmp/rf-eeprom.bin ubi
   mtd -p 0x180000 write /tmp/KeeneticOS-32x6-5.01.C.8.0-2.bin ubi
   mtd write /tmp/uconfig.bin u-boot-env
   ```

4. Kiểm sha256 các vùng vừa ghi (`dd` + `sha256sum`), rồi **ghi FIP sau cùng** và kiểm lại:

   ```bash
   mtd write /tmp/fip-keenetic-32x6.bin fip
   ```

5. Rút điện, cắm lại. Lần đầu U-Boot tạo NMBM (OOB 64, BL2 gốc đọc được) và boot Firmware_1.

### Nâng cấp / web failsafe

Giữ RESET khi cắm điện khoảng 10 giây, PC đặt IP `192.168.1.x` và cắm cáp vào LAN, mở `http://192.168.1.1`. Hoặc dùng
lệnh:

```bash
curl -F "firmware=@KeeneticOS-32x6-5.01.C.8.0-2.bin" http://192.168.1.1/upload
```

Kết quả là `<size> <md5>`. Mở `http://192.168.1.1/flashing.html`, gọi `/result` đến khi ra `success`, rồi
`curl -X POST http://192.168.1.1/reboot`. U-Boot ghi vào ảnh không chạy, chép cấu hình, boot thử; ndm báo
`committed image N`.

### Cứu máy qua UART

UART 115200 8N1, 3,3 V. Không vào được U-Boot thì nạp U-Boot vào RAM (không ghi flash):

```bash
mtk_uartboot -s <cổng> -p bl2-32x6-ram.bin -a -f fip-keenetic-32x6.bin
```

Bật nguồn khi thấy `Handshake...`. Từ U-Boot có thể TFTP rồi `mtd write` lại `fip` / `ubi`, hoặc vào web failsafe.
NMBM hỏng hoặc tạo bằng OOB sai: `mtd erase spi-nand0 0x7800000 0x800000` (vùng quản lý NMBM, chỉ khi không có khối
được ánh xạ: `nmbm nmbm0 mapping` rỗng) rồi để U-Boot OOB 64 tạo lại trước khi rút điện, vì BL2 gốc không tự tạo NMBM.

## Dùng lần đầu

- Wi-Fi `Keenetic`, mật khẩu `12345678` (theo `uconfig.bin`). Web `http://192.168.1.1`.
- Wizard: nhà có modem/router của nhà mạng (ví dụ ONT) thì chọn *Modem/router from your provider* và cắm jack **WAN**
  vào modem. Bỏ qua bước rút điện modem.
- Máy chưa cấu hình có lúc lên ở **chế độ Extender** tại `192.168.1.3` (không có DHCP server). Đặt IP tĩnh
  `192.168.1.x` để vào làm wizard.
- Đèn: đỏ = chưa có Internet, xanh lá = có Internet.
- Nhãn cổng do phần cứng KN-3812 gán cứng: jack WAN là cổng **"1"**, hai jack LAN là **"2"** và **"3"**.

## Giới hạn

- Danh tính (serial, servicetag…) không phải của Keenetic: KeenDNS và dịch vụ cloud không chạy.
- Không cập nhật qua Keenetic: mỗi bản mới phải build lại; script vá nhị phân từ chối nếu `phr.ko` khác bản gốc.
- Máy không có USB. Web vẫn hiện các mục USB như trên KN-3812, nhưng không dùng được.
- Trình kiểm tra Internet của KeeneticOS có thể báo "không có Internet" dù vẫn vào mạng được.
- U-Boot đọc nút RESET chưa có pull-up: đôi khi tưởng RESET đang giữ lúc khởi động (chỉ ghi log, chưa thấy ảnh hưởng).
- Đã thử trên máy: cài, khởi động lạnh, khởi động lại mềm nhiều lần, cấu hình giữ qua khởi động lại, nâng cấp qua
  web failsafe. Chưa thử: chạy lâu ngày, nâng cấp từ web KeeneticOS, nút RESET/WPS lúc đang chạy.
