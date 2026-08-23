# S-081 — 설정 저장 원자화 + 손상 파일 백업

- Status: DONE (2026-08-23 — 상위 직접 수행. pytest 517 passed, ruff 0건)
- Recommended model: **상위 전용**
- 선행: 없음
- Skills to load: task-done
- 근거: 사용자 지시 "전체 기능 설계에 결함은 없는지 다시 살펴보세요" (2026-08-23)

## 목적 (Why) — 데이터 손실

`_save_to_file`이 `json.dump`로 **대상 파일에 직접** 썼다. 파일은 열리는 순간
비워지므로, 쓰는 도중 전원이 나가거나 디스크가 차면 설정이 반쪽으로 남는다.
잘린 파일로 재기동한 실측:

```
파일을 절반으로 절단 (2184 → 1092 바이트)
재기동 후 theme=None, 매크로 0건
설정 폴더의 관련 파일: ['settings.local.json']    ← 백업이 없다
```

백업 장치(`_backup_corrupted_settings`)는 **있었지만 스키마 검증 실패 갈래에만**
걸려 있었다. 그리고 더 나쁜 것이 있었다 — **파싱 실패는 그 두 갈래 어디에도 걸리지
않았다.**

`commentjson`은 파싱 오류를 자체 `JSONLibraryException`으로 감싼다. 이것은
`ValueError`의 하위 클래스가 아니다. 코드 주석은 "commentjson 대비 ValueError를
쓴다"고 적혀 있었지만 실제 예외 타입은 그렇지 않았고, 그래서 가장 흔한 손상인
"잘린 파일"이 맨 끝 `except Exception`으로 떨어져 **백업도 복구 저장도 없이**
조용히 기본값이 됐다.

> 이 결함을 실증하는 과정에서 실제로 개발기의 `settings.local.json`이 날아갔다.
> 백업이 없다는 것이 곧 이 결함의 내용이었다.

## 수행 결과

| 파일 | 변경 |
|---|---|
| `core/settings_manager.py` | 임시 파일 → `fsync` → `os.replace`로 원자적 저장. 실패 시 임시 파일 정리, 원본 보존 |
| `core/settings_manager.py` | `_PARSE_ERRORS` 명시(`ValueError` + `commentjson.JSONLibraryException`), 파싱 실패 갈래에서도 백업 |

수정 후 같은 절단 실험: `settings.local.json.bak`이 남아 원본을 손으로 건질 수 있다.

## 검증

파괴 시험:

| 되살린 결함 | 실패한 테스트 |
|---|---|
| 대상 파일에 직접 쓰기 | `test_save_is_atomic_when_serialization_fails` |
| `ValueError`만 잡기 | `test_truncated_settings_file_is_backed_up_before_reset` |

전원 차단은 흉내 낼 수 없으므로, 원자성이 보장하는 성질 — **실패한 저장이 기존
파일을 훼손하지 않는다** — 를 직렬화 중 예외로 검증한다.

## 남은 사항

`fsync`는 파일 내용만 보장한다. 디렉터리 엔트리까지 보장하려면 부모 디렉터리도
fsync해야 하지만, Windows에서는 디렉터리 핸들 fsync가 표준적으로 동작하지 않아
넣지 않았다. `os.replace`가 같은 볼륨에서 원자적이므로 실용적으로는 충분하다.
