# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all


numpy_datas, numpy_binaries, numpy_hiddenimports = collect_all('numpy')
fr_datas, fr_binaries, fr_hiddenimports = collect_all('face_recognition_models')


a = Analysis(
    ['start.py'],
    pathex=[],
    binaries=numpy_binaries + fr_binaries,
    datas=[('haarcascade_frontalface_default.xml', '.'), ('person.db', '.'), ('images', 'images')] + numpy_datas + fr_datas,
    hiddenimports=['face_recognition_models', 'dlib', 'zeep'] + numpy_hiddenimports + fr_hiddenimports,
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
    name='SecurityFaceDetection',
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
