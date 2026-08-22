"""
env_bootstrap.py — 동적 계측 공유 부트스트랩 (TASK-002/005/006/014 공용)

목적: 이 개발 머신에는 STOM 암호화 키 레지스트리(HKLM\\SOFTWARE\\WOW6432Node\\
STOM\\EN_KEY)가 없어, `ui.main_window` import 체인이 실행하는 모듈 최상위
`load_settings()`가 `read_key()`에서 FileNotFoundError로 실패한다
(utility/settings/setting_user.py:11 — try 블록 밖).

이 헬퍼는 **시스템/레지스트리에 아무것도 쓰지 않고** 격리 프로세스 안에서만
`utility.static_method.static_fernet_key.read_key`를 임시 Fernet 키로 몽키패치해
그 실패를 우회한다. 임시 키는 프로세스마다 새로 생성되며 어디에도 저장되지 않는다
(pyd-analysis 스킬의 "가짜 키 + DB 사본" 원칙과 일치, RULES.md §4 비밀값 보호 준수).

주의:
- `install()`은 반드시 `ui`/`utility` 패키지에서 load_settings를 유발하는 어떤
  import보다 **먼저** 호출한다.
- 실제 저장된 시크릿(access_key/secret_key/시리얼키 등)은 이 임시 키로 복호화되지
  않아 load_settings 내부에서 InvalidToken으로 처리되고 호출부가 기본값 폴백한다.
  이는 의도된 동작이다 — 실제 시크릿을 절대 읽지 않는다.
- 원격 인증 코드는 이 부트스트랩으로도 실행하지 않는다 (TASK-007/RULES.md §4).
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

_installed = False
_ephemeral_key: str | None = None
_temp_dirs: list[str] = []


def _new_fernet_key() -> str:
    """프로세스별 임시 Fernet 키 1개 생성 (str, REG_SZ 반환값과 동일 형태)."""
    from cryptography.fernet import Fernet
    return Fernet.generate_key().decode("utf-8")


def install(offscreen: bool = True, patch_read_key: bool = True) -> str:
    """부트스트랩을 적용하고 사용된 임시 Fernet 키를 반환한다 (idempotent).

    - offscreen=True: QT_QPA_PLATFORM=offscreen 설정 (모든 Qt import 전 필수)
    - patch_read_key=True: static_fernet_key.read_key를 임시 키 반환으로 교체
    - 저장소 루트를 sys.path에 삽입해 `import ui.main_window`가 해소되게 함
    """
    global _installed, _ephemeral_key
    if _installed:
        return _ephemeral_key  # type: ignore[return-value]

    if offscreen:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    _ephemeral_key = _new_fernet_key()

    if patch_read_key:
        # static_fernet_key 모듈 import 자체는 부작용이 없다(함수 정의만; winreg/
        # Fernet은 함수 내부에서 지연 import). read_key 속성만 교체하면,
        # load_settings가 함수 실행 시점에 `from ... import read_key`로 재바인딩할 때
        # 이 임시 버전을 가져간다.
        import utility.static_method.static_fernet_key as fk

        key = _ephemeral_key
        fk.read_key = lambda: key  # type: ignore[assignment]

    _installed = True
    return _ephemeral_key


def temp_db_copy(src_db_dir: str | os.PathLike | None = None) -> str:
    """실제 _database/를 임시 디렉터리로 복사하고 그 경로를 반환한다.

    원본 DB에 어떤 쓰기도 발생하지 않도록 계측 하네스(TASK-005)가 사용한다.
    반환된 경로를 setting_base의 DB 경로로 지정하는 것은 호출부 책임이다.
    TASK-002(import+리플렉션)에는 불필요.
    """
    src = Path(src_db_dir) if src_db_dir else (REPO_ROOT / "_database")
    dst = Path(tempfile.mkdtemp(prefix="stom_dbcopy_"))
    if src.exists():
        shutil.copytree(src, dst / src.name)
    _temp_dirs.append(str(dst))
    return str(dst / src.name)


def get_key() -> str | None:
    """install()이 사용한 임시 Fernet 키를 반환한다 (미설치 시 None)."""
    return _ephemeral_key


def redirect_paths(base_dir: str | os.PathLike) -> None:
    """setting_base의 경로 상수 전부를 base_dir 하위로 재지정한다.

    setting_base는 상수만 정의하므로 속성 재대입으로 안전하게 우회할 수 있다.
    setting_user.load_settings / database_check는 이 상수들을 (함수 또는 모듈)
    import 시점에 바인딩하므로, 이 함수를 그들 import/호출보다 먼저 실행해야 한다.
    파생 상수(DB_SETTING 등)는 원본 f-string 공식대로 개별 재계산한다.
    """
    import utility.settings.setting_base as sb

    base = Path(base_dir)
    db = (base / "_database").as_posix()
    back = (base / "backtest").as_posix()
    sb.DB_PATH = db
    sb.LOG_PATH = (base / "_log").as_posix()
    sb.BACK_PATH = back
    sb.GRAPH_PATH = f"{back}/_graph"
    sb.BACK_TEMP = f"{back}/_temp"
    sb.DB_SETTING = f"{db}/setting.db"
    sb.DB_BACKTEST = f"{db}/backtest.db"
    sb.DB_TRADELIST = f"{db}/tradelist.db"
    sb.DB_STRATEGY = f"{db}/strategy.db"
    sb.DB_CODE_INFO = f"{db}/code_info.db"
    sb.DB_OPTUNA = f"sqlite:///{db}/optuna.db"


def make_fixture_workspace() -> str:
    """임시 디렉터리에 STOM 기본 DB 픽스처를 생성하고 base 경로를 반환한다.

    - 모든 DB 경로를 임시 디렉터리로 재지정 (실제 _database/ 미생성)
    - STOM 자체 초기화 루틴 database_check()로 기본 setting.db 등을 생성.
      read_key는 install()에서 이미 패치돼 있어 database_check가 write_key()
      (레지스트리 쓰기)를 타지 않는다. 기본 행은 암호화 필드가 비어 있어
      복호화(InvalidToken)도 발생하지 않는다 → load_settings가 정상 dict 반환.
    - 반드시 install() 이후, 그리고 어떤 ui/utility 위젯 import보다 먼저 호출한다.
    """
    if not _installed:
        install()
    base = tempfile.mkdtemp(prefix="stom_fixture_")
    _temp_dirs.append(base)
    redirect_paths(base)
    from utility.db_control.database_check import database_check

    ok, msg = database_check()
    if not ok:
        raise RuntimeError(f"database_check() 실패: {msg}")
    return base


def cleanup() -> None:
    """생성한 임시 DB 사본/픽스처 디렉터리를 제거한다."""
    for d in _temp_dirs:
        shutil.rmtree(d, ignore_errors=True)
    _temp_dirs.clear()
