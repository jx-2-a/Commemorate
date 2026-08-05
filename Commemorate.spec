# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py', 'app_config.py', 'login_window.py', 'update_manager.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config.json', '.'),
        ('TimerPageWords.csv', '.'),
    ],
    hiddenimports=['PyQt5.QtNetwork', 'PyQt5.QtMultimedia',
                   'PyQt5.QtMultimediaWidgets'],
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
    a.binaries,
    a.datas,
    [],
    name='Commemorate',
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
