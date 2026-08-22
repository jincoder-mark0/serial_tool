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
"""

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
