# -*- mode: python ; coding: utf-8 -*-
"""
SerialTool PyInstaller 스펙 (S-012)

WHY: 독립 실행 파일 배포 (doc/task.md Phase 8).
     onedir 모드 사용 — onefile은 시작이 느리고 백신 오탐이 잦다.
WHAT: main.py를 진입점으로 하고 resources/ 전체를 datas로 번들한다.
      아이콘(.ico)은 resources/icons/에 없으므로 지정하지 않는다 (후속 보고 대상).
HOW: `.venv\\Scripts\\pyinstaller serial_tool.spec --noconfirm` 로 빌드.
     resources/ 경로는 core/resource_path.py가 sys._MEIPASS 기준으로 찾는다
     (onedir이므로 _MEIPASS는 dist/SerialTool/_internal — 임시 해제 폴더가 아님).
     빌드 도구는 requirements-build.txt로 설치한다.
"""

import os

# 번들에서 제외할 개발자 로컬 파일.
#
# WHY: `datas=[('resources', 'resources')]`는 디렉터리를 통째로 담으므로 git이
#      추적하지 않는 파일까지 artifact에 들어간다. `settings.local.json`은
#      S-043이 "개발자 로컬 세션이 커밋에 섞이는 오염"을 막으려고 분리하고
#      .gitignore에 넣은 파일인데, 그 보호가 git에서만 작동해 빌드로는 그대로
#      새어나갔다 — 빌드한 개발자의 창 위치/포트 탭/입력값이 배포본에 실린다.
#      번들 실행 시 사용자 설정은 APPDATA를 쓰므로
#      (resource_path.user_settings_file) 이 파일은 읽히지도 않는 순수 유출이고,
#      빌드하는 사람마다 artifact가 달라져 재현성도 깨진다.
EXCLUDED_DATA_BASENAMES = {'settings.local.json'}

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('resources', 'resources')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
# 개발자 로컬 파일을 번들에서 걷어낸다 (위 EXCLUDED_DATA_BASENAMES 참고).
a.datas = [
    entry for entry in a.datas
    if os.path.basename(entry[0]) not in EXCLUDED_DATA_BASENAMES
]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SerialTool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon: resources/icons/ 에 .ico 파일이 없어 미지정 (변환 작업은 범위 밖 — 후속 보고)
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SerialTool',
)
