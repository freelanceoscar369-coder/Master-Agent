# PyInstaller spec — Kalpavriksha Founder Edition Desktop Alpha.
# Build with: pyinstaller packaging/kalpavriksha.spec --noconfirm
#
# Bundles kalpavriksha_desktop.py (the pywebview host) together with the
# whole master_agent backend it imports, the desktop_app/web/ frontend as
# data files, and the tree-mark icon. No backend module is rewritten or
# duplicated here — this is packaging, not implementation.

import os

block_cipher = None
ROOT = os.path.abspath(os.path.join(os.path.dirname(SPEC), '..'))

a = Analysis(
    [os.path.join(ROOT, 'kalpavriksha_desktop.py')],
    pathex=[os.path.join(ROOT, 'src')],
    binaries=[],
    datas=[
        (os.path.join(ROOT, 'desktop_app', 'web'), 'web'),
        (os.path.join(ROOT, 'desktop_app', 'voice_models'), 'voice_models'),
    ],
    # `voice_models/` now also holds `whisper-base.en/` (the bundled
    # faster-whisper CTranslate2 model — see kalpavriksha_desktop.py's
    # `_whisper_model_path()`), collected by the single `voice_models` datas
    # entry above since it copies the whole directory tree.
    hiddenimports=[
        'webview',
        'webview.platforms.edgechromium',
        'webview.platforms.winforms',
        'master_agent',
        'master_agent.founder_edition',
        'master_agent.founder_edition.desktop_shell',
        'master_agent.founder_edition.voice_pipeline',
        'master_agent.founder_edition.console',
        'master_agent.communication',
        'master_agent.conversation_engine',
        'master_agent.founder_identity',
        'master_agent.founder_runtime',
        'master_agent.desktop',
        'master_agent.desktop.execution',
        'master_agent.desktop.perception',
        'master_agent.desktop.operations',
        'master_agent.desktop_operator',
        'master_agent.environment_intelligence',
        'master_agent.vigilance',
        'master_agent.memory',
        'sounddevice',
        'faster_whisper',
        'ctranslate2',
        'piper',
        'piper.voice',
        'onnxruntime',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['master_agent.launcher', 'master_agent.dashboard', 'master_agent.mission_control'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Kalpavriksha',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # no terminal — a desktop product, per the mission brief
    icon=os.path.join(ROOT, 'desktop_app', 'assets', 'kalpavriksha.ico'),
    version=os.path.join(ROOT, 'packaging', 'version_info.py'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='Kalpavriksha',
)
