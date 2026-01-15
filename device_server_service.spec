# spec file for creating the device server Windows service executable
# To build: pyinstaller device_server_service.spec

# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['device_server_srv.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Include any additional files if needed
    ],
    hiddenimports=[
        'win32timezone',  # Commonly needed for win32 services
        'mysql.connector',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='hip_device_service',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Hide console window for service
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add an icon if you have one
)