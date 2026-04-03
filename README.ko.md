# Turing Smart Screen - TrueNAS 시스템 모니터

**3.5인치 USB LCD 모니터** (Turing Smart Screen / USB35INCHIPSV2)에 TrueNAS 시스템 상태를 실시간으로 표시하는 Python 스크립트입니다.

![demo](screenshot.png)

## 지원 하드웨어

- **3.5인치 IPS USB LCD 모니터** (알리익스프레스에서 흔히 판매)
- Vendor ID: `1a86` (QinHeng Electronics)
- Product ID: `5722`
- 장치명: `UsbMonitor`
- 시리얼: `USB35INCHIPSV2`
- 해상도: 480x320
- 인터페이스: USB CDC-ACM (`/dev/ttyACM0`)
- 호환 소프트웨어: TURMO, UsbMonitor.exe

## 표시 항목

- CPU 사용률 (색상 바)
- RAM 사용률
- 디스크 사용량 (풀별)
- 온도 센서
- 실시간 네트워크 업로드/다운로드 속도
- 누적 네트워크 트래픽
- 시스템 가동 시간
- IP 주소

## 프로토콜 상세

이 장치는 **Turing Smart Screen Revision A** 프로토콜을 사용합니다:

1. **핸드셰이크**: `[0x45] * 6` 전송, `[0x01] * 6` 수신 (3.5인치 장치)
2. **방향 설정**: 16바이트 명령, 바이트 6에 방향 코드
   - `100` = 세로, `101` = 가로, `102` = 세로 반전, `103` = 가로 반전
3. **비트맵 표시**: 6바이트 좌표 패킹 명령(cmd=197) 후 RGB565 리틀엔디안 픽셀 데이터를 `width * 8` 바이트 단위로 전송
4. **시리얼**: 115200 baud, RTS/CTS 흐름 제어

### 명령 포맷 (6바이트)

```
Byte 0: x >> 2
Byte 1: ((x & 3) << 6) | (y >> 4)
Byte 2: ((y & 15) << 4) | (ex >> 6)
Byte 3: ((ex & 63) << 2) | (ey >> 8)
Byte 4: ey & 255
Byte 5: command_id
```

### 주요 명령 ID

| 명령 | ID | 설명 |
|------|-----|------|
| HELLO | 69 | 핸드셰이크 |
| CLEAR | 102 | 화면 지우기 |
| SCREEN_OFF | 108 | 백라이트 끄기 |
| SCREEN_ON | 109 | 백라이트 켜기 |
| SET_BRIGHTNESS | 110 | 밝기 설정 (0=최대, 255=끄기) |
| SET_ORIENTATION | 121 | 화면 방향 설정 |
| DISPLAY_BITMAP | 197 | 이미지 데이터 전송 |

## 빠른 시작

### Docker (권장)

```bash
# 빌드
docker build -t usb-lcd .

# 실행
docker run -d \
  --name usb-lcd \
  --restart unless-stopped \
  --privileged \
  --pid host \
  -v /dev/ttyACM0:/dev/ttyACM0 \
  -v /mnt:/mnt:ro \
  usb-lcd
```

### 수동 설치

```bash
pip install pyserial psutil Pillow
python3 monitor.py
```

## 설정 변경

`monitor.py`에서 수정 가능:

- `PORT` - 시리얼 포트 (기본: `/dev/ttyACM0`)
- `buf[6]` - 화면 방향 (`100`~`103`)
- 디스크 경로 - `/mnt/StorageSamsung`, `/mnt/StorageSeagate`를 본인 풀 경로로 변경
- 색상, 레이아웃, 폰트 - 렌더링 섹션 수정

## TrueNAS 설치 방법

1. USB LCD를 TrueNAS 미니PC에 연결
2. `/dev/ttyACM0`으로 인식되는지 확인:
   ```bash
   dmesg | grep ttyACM
   ```
3. Docker로 실행 (위 참조)

## 문제 해결

- **화면이 깨짐**: 프로토콜이 맞지 않음. HELLO 명령에 `010101010101` 응답이 오는지 확인.
- **화면 표시 안 됨**: `/dev/ttyACM0` 존재 확인. `ls /dev/ttyACM*` 실행.
- **색상이 이상함**: RGB565 리틀엔디안 사용. 색상이 뒤바뀌면 바이트 순서 확인.
- **화면이 뒤집힘**: 스크립트에서 방향 코드(100~103) 변경.

## 참고

- TURMO Windows 애플리케이션에서 프로토콜 역분석
- 참고: [turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python) Revision A 프로토콜 문서

## 라이선스

MIT
