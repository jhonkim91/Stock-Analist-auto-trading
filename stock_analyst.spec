# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: Stock Analyst를 단일 실행 파일(.exe)로 패키징한다.

빌드:
    py launcher.py build-exe
    # 또는: .venv\\Scripts\\python -m PyInstaller --noconfirm stock_analyst.spec

산출물: dist/StockAnalyst.exe (단일 파일)
런타임 데이터(SQLite DB, reports)는 .exe와 같은 폴더의 backend/data, backend/reports에 생성된다.
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# 백엔드 전체 모듈을 포함해 동적 참조 누락을 방지한다.
hidden_imports = collect_submodules("backend")
# uvicorn은 프로토콜/루프 구현을 런타임에 동적 import 한다.
hidden_imports += [
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
]

# 번들에 포함할 읽기 전용 데이터:
#  - backend/config/*.yaml  → backend/config (런타임 설정)
#  - frontend/out           → frontend_out  (정적 UI; main.py가 _MEIPASS/frontend_out에서 찾음)
datas = [
    ("backend/config", "backend/config"),
    ("frontend/out", "frontend_out"),
]
# pandas/numpy 등 패키지 데이터는 대부분 자체 hook이 처리하지만, 누락 대비로 명시 수집.
datas += collect_data_files("pandas")


a = Analysis(
    ["app_main.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="StockAnalyst",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
