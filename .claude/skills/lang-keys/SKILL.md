---
name: lang-keys
description: SerialTool 다국어(언어 키) 추가·변경 절차 — en/ko JSON 동기화, [TODO] 제거, 검증
---

# lang-keys — 언어 키 추가·변경 절차

UI에 보이는 문자열을 추가·변경할 때 이 절차를 따른다. 위젯 코드에 한글/영문 하드코딩 금지.

## 규칙

- 리소스: `resources/languages/en.json`(기준어) / `ko.json`. 코드에서는 `LanguageManager` 경유로 조회.
- 키 형식: `[context]_[type]_[name]` — 예: `port_btn_connect`, `macro_lbl_delay`, `file_msg_transfer_done`.
  기존 키의 context/type 어휘를 먼저 검색해 재사용한다 (새 어휘 발명 금지).
- 영어 fallback이 있으므로 en.json이 정본이다 — en에 먼저 넣는다.

## 절차

```powershell
# 1. en.json에 키·영문 텍스트 추가 (알파벳 정렬 위치 무시해도 됨 — 3에서 정렬됨)
# 2. 코드에서 키 사용 (위젯의 retranslate/tr 경로에 연결)

# 3. ko.json 동기화 — 누락 키에 [TODO] 템플릿 생성 + 양쪽 정렬
.venv\Scripts\python tools\manage_language_keys.py

# 4. ko.json의 [TODO] 항목을 실제 한국어 번역으로 교체

# 5. 검증 — 키 누락·[TODO] 잔존 시 exit 1
.venv\Scripts\python tools\check_language_keys.py
$env:QT_QPA_PLATFORM="offscreen"; .venv\Scripts\python -m pytest tests/test_view_translations.py -q
```

## 주의

- `[TODO]`를 남긴 채 완료 선언 금지 — check_language_keys가 잡는다.
- 키 삭제 시 en/ko 양쪽에서 지우고, 코드의 사용처가 없는지 Grep으로 확인한다.
- 언어 전환은 런타임 실시간 반영이다 — 새 위젯은 언어 변경 시 재번역되는 경로(retranslate 관례)에
  텍스트 설정을 두어야 한다. 생성자에서 한 번만 설정하면 전환 시 텍스트가 남는다.
