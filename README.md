# KeeneticOS cho Viettel vAP-32X6V1

Chạy KeeneticOS (bản KN-3812 Hopper SE) trên 32x6 **song song với OpenWrt**, dùng U-Boot Multi Firmware của
OpenWrt (`OpenWRT/README-viettel-32x6.md`). KeeneticOS nằm ở 32 MiB cuối NAND, ngoài UBI; OpenWrt, ImmortalWrt
và recovery vẫn ở UBI. Giữ nút **Mesh** khi cắm điện là về OpenWrt.

Repo gồm bản vá và script. Phần mềm đóng của Keenetic (ndm, web UI, driver) được lấy lúc build từ ảnh KN-3812
chính hãng đặt trong `stock/`.

## Layout NAND (128 MiB)

```
0x0000000  BL2
0x0100000  U-Config     danh tính Keenetic (vùng u-boot-env cũ)
0x0180000  Factory      MAC + calibration Wi-Fi (KeeneticOS không đụng tới)
0x0380000  FIP          U-Boot Multi Firmware
0x0580000  ubi          OpenWrt, ImmortalWrt, recovery, env U-Boot (90,5 MiB)
0x6000000  keenetic     KeeneticOS (32 MiB, bên dưới)
```

Trong `keenetic`:

| Địa chỉ | Phân vùng | Kích thước |
|---|---|---|
| 0x6000000 | Firmware_1 (Kernel_1 + RootFS_1) | tối đa 30 MiB |
| 0x7e00000 | Config_1 | 512 KiB |
| 0x7e80000 | Config_2 | 512 KiB |
| 0x7f00000 | U-State | 128 KiB |
| 0x7f20000 | Dump | 128 KiB |
| 0x7f40000 | D-State | 128 KiB |
| 0x7f60000 | RF-EEPROM | 640 KiB (bản sao Factory 0x0–0xa0000, MAC LAN ở 0x4, WAN ở 0xa) |

Không có NMBM và chỉ có một ảnh. ndm chạy ở chế độ dual-image nên vẫn cần Config_2 (`Backup::ConfigStorage`)
và D-State (`Update::Manager`); thiếu một trong hai là ndm thoát và máy khởi động lại liên tục.

## Những gì được sửa

| File | Tác dụng |
|---|---|
| `kernel/402-ndmpart-viettel-32x6-layout.patch` | ndmpart chia phân vùng trên SPI-NAND thô (bỏ NMBM), chỉ ảnh 1 |
| `kernel/406-ndmpart-di-viettel-32x6.patch` | U-State ngay sau giới hạn flash (0x7f00000); chưa có U-State thì dùng mặc định trong RAM |
| `kernel/407-ndmpart-config2-viettel-32x6.patch` | Thêm Config_2 và D-State, chuyển Dump (layout ở trên) |
| `kernel/KN-3812.dts` | RAM 256 MiB, bỏ NMBM và USB, `/chosen/dualimage` (ndm cần `/proc/dual_image`), pull-up cho nút RESET/WPS (không có thì ndm reset cấu hình mỗi lần khởi động lạnh), giữ GPIO 39 (reset MT7531) mức cao, tắt LED đỏ/xanh dương và hai chân phụ của LED xanh lá |
| `kernel/config-4.9.additions` | pstore; `apply-to-sdk.sh` đặt `CONFIG_MTD_NDM_FLASH_SIZE_LIMIT=0x7f00000` |
| `binpatch/phr_32x6_patch.py` | `phr.ko`: nút RESET GPIO 1, nút WLAN (WPS) GPIO 0; LED trạng thái KN-3812 (xanh/cam) → xanh lá GPIO 8 / đỏ GPIO 5; không USB; GPIO 39 mức cao |
| `rootfs/ndm_default_config_32x6.py` | Cấu hình mặc định: ISP = GigabitEthernet0/0 (jack WAN, VLAN 2), GigabitEthernet1 + 1/0 (PHY SoC, không có jack) tắt, tên "Viettel vAP-32X6V1", **tắt auto-update** |
| `rootfs/webui_32x6.py` | Web UI và wizard theo phần cứng 32x6: 3 cổng (WAN xanh dương = GigabitEthernet0/0, LAN = 0/1, 0/2; bỏ GigabitEthernet1/0 không có jack) ở hình cổng, *Network Ports* và thống kê; wizard lấy jack WAN làm cổng Internet; model `vAP-32X6V1` ở header, trang đăng nhập và wizard |
| `tools/mk_keenetic_data.py` | Tạo `uconfig.bin` (danh tính sinh cố định từ Factory, Wi-Fi mặc định `Keenetic` / `12345678`) và `rf-eeprom.bin` từ bản dump Factory |
| `stock/` | Ảnh KN-3812 chính hãng (`.bin`, không commit), danh sách thành phần của nó (`.txt`) và sha256 |
| `debug/` | Overlay rootfs cho bản build gỡ lỗi (`DEBUG=1`) |

Auto-update phải tắt và **không bao giờ nạp ảnh KN-3812 chính hãng lên máy**: ảnh đó dùng NMBM `forced-create` trên
toàn NAND, phá UBI của OpenWrt. `multifw flash keenetic` từ chối ảnh không phải bản build 32x6.

## Ảnh chính hãng (`stock/`)

`KN-3812_stable_5.1.8_5.01.C.8.0-2.bin` là firmware Keenetic Hopper SE (KN-3812) bản 5.1.8 stable, mã build
5.01.C.8.0-2. File `.txt` cùng tên là danh sách thành phần của ảnh đó, cùng định dạng dòng `components` của
`show version`. Lúc build, danh sách này được đưa nguyên vẹn cho `configure.sh -p manual KN-3812` của SDK. Không bỏ
thành phần nào (kể cả USB/lưu trữ): bỏ chúng làm thay đổi bộ driver mạng nạp lúc khởi động, và `hw_nat.ko` sẽ panic
trong `ppe_init`, khiến máy khởi động lại liên tục.

Ảnh `.bin` là phần mềm đóng của Keenetic nên không commit vào git (`.gitignore`), giống repo NR3053. Clone mới thì
tải đúng bản 5.01.C.8.0-2 của KN-3812 từ Keenetic, đặt vào `stock/`, rồi kiểm tra:

```bash
cd keenetic-32x6/stock
curl -fLO https://osvault.keenetic.ru/KN-3812/5.01/KN-3812_stable_5.1.8_5.01.C.8.0-2.bin
sha256sum -c sha256sums
```

### Build trên GitHub

Actions → **Build KeeneticOS for Viettel 32x6** → Run workflow, chọn nhánh. Workflow tải ảnh gốc ở trên, build
KeeneticOS, rồi tạo release có tag là mã build của KeeneticOS: `5.01.C.8.0-2-multifw` cho nhánh này,
`5.01.C.8.0-2` cho nhánh độc lập `5.1.8`. Build lại cùng phiên bản thì release cũ bị thay. `uconfig.bin` và
`rf-eeprom.bin` không có trong release vì mỗi router một khác.

## Build

Cần WSL/Linux như hướng dẫn của SDK (thêm `xxd kmod bison flex`) và SDK cùng phiên bản:

```bash
git clone --depth 1 -b 5.01.C.8.0-2 https://github.com/keenetic/keenetic-sdk.git ~/keenetic-sdk
```

```bash
bash keenetic-32x6/scripts/build-wsl.sh
```

Script chép repo sang `~/kn-32x6-port`, chạy `scripts/apply-to-sdk.sh`, rồi `make`. Bước apply gồm: vá kernel, DTS,
config, `unpack.sh` ảnh trong `stock/`, chọn thành phần, vá `phr.ko`, sửa default-config và web UI. Ảnh ra ở
`~/keenetic-sdk/bin/mt7981/*KN-3812*.bin`. Đổi phần kernel thì chạy `make target/linux/clean` trong SDK trước.

**Bản gỡ lỗi** (`DEBUG=1 bash keenetic-32x6/scripts/build-wsl.sh`): init chạy `/etc/dbg.sh` thay cho ndm. Script
chạy ndm dưới strace, chép log syslog của ndm, trạng thái cổng và cấu hình vào log kernel, rồi khởi động lại sau
120 s. Giữ Mesh (không rút điện) để U-Boot lưu log, sau đó xem bằng `multifw keenetic-log`. `/bin/sh` của KeeneticOS
là "NDM Shell Wrapper" chạy script bằng `/opt/bin/sh`, nên bản gỡ lỗi đặt một busybox có `sh` ở đó.

## Cài

KeeneticOS chỉ chạy được trên U-Boot Multi Firmware với layout mới (UBI kết thúc ở 0x6000000, có phân vùng
`keenetic` và `U-Config`), và được cài từ OpenWrt. Cách bắt đầu tuỳ máy đang chạy gì:

| Máy đang chạy | Làm gì |
|---|---|
| Firmware Viettel gốc | Backup, cài OpenWrt Multi Firmware theo mục 4 của `OpenWRT/README-viettel-32x6.md`, rồi làm *Cài từ OpenWrt* bên dưới |
| OpenWrt Multi Firmware, layout mới | *Cài từ OpenWrt* (đang ở ImmortalWrt slot 2 thì `boot` về OpenWrt trước) |
| OpenWrt/ImmortalWrt thường (không Multi Firmware), hoặc Multi Firmware layout cũ (UBI 122,5 MB, có slot 3) | Ghi FIP Multi Firmware, để U-Boot tạo lại UBI rồi cài OpenWrt (mục 4, *Từ OpenWrt/ImmortalWrt khác*). **Mọi firmware trong UBI bị xoá.** Sau đó *Cài từ OpenWrt* |
| KeeneticOS bản cũ của repo này | Về OpenWrt (giữ Mesh khi cắm điện), `multifw flash keenetic` ảnh mới; cấu hình giữ nguyên |
| Keenetic cài đè cả flash (KeenBOOT, bootloader và layout của Keenetic) | Cần UART: Factory và có thể cả BL2 đã bị ghi đè (mục 4, *Từ Keenetic cài đè cả flash*). Sau đó *Cài từ OpenWrt* |
| Ảnh KN-3812 chính hãng | **Không bao giờ** (xem trên) |

### Cài từ OpenWrt

Trên PC, tạo danh tính và RF-EEPROM từ Factory của **chính router này**:

```bash
ssh root@192.168.1.1 'cat /dev/mtd2ro' > factory.bin
```

```bash
python3 keenetic-32x6/tools/mk_keenetic_data.py factory.bin kn-data
```

Chép `kn-data/*.bin` và ảnh build lên `/tmp` của router (`scp -O`), rồi:

```bash
multifw keenetic-init /tmp/uconfig.bin /tmp/rf-eeprom.bin
```

```bash
multifw flash keenetic /tmp/<ảnh>.bin
```

```bash
multifw boot keenetic
```

Hoặc dùng LuCI *Advanced → Đa firmware*, dòng KeeneticOS (sau `keenetic-init`). `keenetic-init` chỉ làm một lần, vì
nó xoá cả vùng `keenetic` (kể cả cấu hình). Muốn đổi Wi-Fi mặc định trong `uconfig.bin` mà không xoá gì:
`mtd write /tmp/uconfig.bin U-Config`.

- `multifw flash keenetic` nạp bản mới và giữ cấu hình.
- `multifw reset keenetic` xoá cấu hình KeeneticOS (Config_1 và Config_2).

Về OpenWrt: giữ nút Mesh khi cắm điện (đèn xanh dương sáng). U-Boot lưu log kernel của lần chạy KeeneticOS vừa rồi
vào volume `kn_log`; xem bằng `multifw keenetic-log`.

## Dùng lần đầu

- Wi-Fi `Keenetic`, mật khẩu `12345678` (theo `uconfig.bin`). Web `http://192.168.1.1`.
- Wizard: nhà có modem/router của nhà mạng (ví dụ ONT) thì chọn *Modem/router from your provider* và cắm jack **WAN**
  vào modem. Bỏ qua bước rút điện modem.
- Máy chưa cấu hình có lúc lên ở **chế độ Extender**: mạng Home lấy IP qua DHCP, không ai cấp thì tự dùng
  `192.168.1.3` và không có DHCP server (Wi-Fi không cấp IP). Vào `http://192.168.1.3` từ máy đặt IP tĩnh
  `192.168.1.x` để làm wizard.
- Đèn: đỏ = chưa có Internet, xanh lá = có Internet.
- Nhãn cổng do phần cứng KN-3812 gán cứng: jack WAN là cổng **"1"**, hai jack LAN là **"2"** và **"3"**.

Ảnh cũ (trước `webui_32x6.py`) để wizard đặt WAN lên GigabitEthernet1, không có jack. Sửa bằng CLI
(SSH, hoặc POST `/rci/` với `[{"parse": "<lệnh>"}]`), rồi `system configuration save`:

```
interface GigabitEthernet0/Vlan2
interface GigabitEthernet0/Vlan2 security-level public
interface GigabitEthernet0/Vlan2 ip address dhcp
interface GigabitEthernet0/Vlan2 ip global 700
interface GigabitEthernet0/Vlan2 up
interface GigabitEthernet0/0 switchport access vlan 2
interface GigabitEthernet0/0 role inet for GigabitEthernet0/Vlan2
interface GigabitEthernet1 down
```

## Giới hạn

- Danh tính (serial, servicetag…) không phải của Keenetic: KeenDNS và dịch vụ cloud không chạy.
- Không cập nhật từ web KeeneticOS; mỗi bản mới phải build lại, script vá nhị phân sẽ từ chối nếu `phr.ko` khác bản gốc.
- Máy không có USB và Storage. Web vẫn hiện các mục USB, ổ đĩa và ứng dụng như trên KN-3812, nhưng không dùng được.
- Khối NAND hỏng trong vùng `keenetic` không được thay thế (`multifw` từ chối nếu có).
- Chỉ có một ảnh: không có ảnh dự phòng của KeeneticOS.
