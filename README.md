# NEON KEYS

떨어지는 타일을 순서대로 탭하는 리듬 게임 (Python + pygame).

## 다운로드 (Windows)

[Releases](../../releases/latest)에서 `NeonKeys-Windows.zip`을 받아 압축을 풀고 `NeonKeys.bat`을 더블클릭하면 됩니다.
파이썬 설치나 인터넷 연결이 필요 없습니다 (64비트 Windows).

## 소스로 실행 (macOS / Linux / Windows)

```bash
pip install pygame
python main.py
```

## 조작

| 키 | 동작 |
|---|---|
| `D` `F` `J` `K` / 마우스 클릭 | 해당 레인 탭 |
| `←` `→` | 시작 화면에서 곡 선택 |
| `Space` / 클릭 | 재시작 |
| `Esc` | 종료 |

맨 아래 빛나는 타일을 탭하세요. 다른 레인을 누르거나 타일을 놓치면 게임오버입니다.

## 곡

FREE PLAY, Twinkle Star, Ode to Joy, Für Elise, Canon in D — 모두 저작권이 만료된 곡입니다.

### 내 MIDI 불러오기

`main.py` 옆의 `songs/` 폴더에 `.mid` 파일을 넣고 게임을 다시 켜면 곡 목록에 추가됩니다.
가장 멜로디에 가까운 트랙의 음을 순서대로 뽑아 타일 하나에 음 하나씩 연주합니다 (박자는 치는 속도를 따릅니다).
`songs/` 안의 MIDI 파일은 저장소에 올라가지 않습니다. 사용할 권리가 있는 파일만 넣으세요.
