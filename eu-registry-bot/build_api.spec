# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for API server

block_cipher = None

a = Analysis(
    ['api/server.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config', 'config'),
        ('src', 'src'),
    ],
    hiddenimports=[
        'flask',
        'flask_cors',
        'selenium',
        'selenium.webdriver',
        'selenium.webdriver.chrome',
        'selenium.webdriver.chrome.service',
        'selenium.webdriver.chrome.options',
        'selenium.webdriver.common.by',
        'selenium.webdriver.support',
        'selenium.webdriver.support.ui',
        'selenium.webdriver.support.expected_conditions',
        'webdriver_manager',
        'webdriver_manager.chrome',
        'cryptography',
        'OpenSSL',
        'apscheduler',
        'apscheduler.schedulers.background',
        'apscheduler.triggers.cron',
        'yaml',
        'pydantic',
        'colorlog',
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
    name='api_server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Set to False to hide console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
