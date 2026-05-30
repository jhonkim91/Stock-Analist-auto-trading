# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: Stock Analyst를 단일 실행 파일(.exe)로 패키징한다.

데스크톱 네이티브 창(pywebview/WebView2) 모드로 빌드된다 — 콘솔창 없이 일반
Windows 프로그램처럼 동작한다.

빌드:
    py launcher.py build-exe
    # 또는: .venv\\Scripts\\python -m PyInstaller --noconfirm stock_analyst.spec

산출물: dist/StockAnalyst.exe (단일 파일)
런타임 데이터(SQLite DB, reports, logs)는 .exe와 같은 폴더의 backend/ 아래에 생성된다.
"""

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

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
datas += collect_data_files("pandas")

binaries = []

# 데스크톱 창 백엔드(pywebview + pythonnet/clr). 설치돼 있지 않으면(예: 비-Windows
# 빌드) 조용히 건너뛴다 — 런타임에 app_main이 브라우저로 폴백한다.
for _pkg in ("webview", "clr_loader", "pythonnet"):
    try:
        _d, _b, _h = collect_all(_pkg)
        datas += _d
        binaries += _b
        hidden_imports += _h
    except Exception:
        pass
hidden_imports += ["clr"]


a = Analysis(
    ["app_main.py"],
    pathex=["."],
    binaries=binaries,
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
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
