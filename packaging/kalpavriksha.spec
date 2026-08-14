# PyInstaller spec — Kalpavriksha Founder Edition Desktop Alpha.
# Build with: pyinstaller packaging/kalpavriksha.spec --noconfirm
#
# Bundles kalpavriksha_desktop.py (the pywebview host) together with the
# whole master_agent backend it imports, the desktop_app/web/ frontend as
# data files, and the tree-mark icon. No backend module is rewritten or
# duplicated here — this is packaging, not implementation.

import os
import piper as _piper_pkg  # resolve espeak-ng-data from the installed package
import playwright as _playwright_pkg  # resolve the bundled Node driver from the installed package

block_cipher = None
ROOT = os.path.abspath(os.path.join(os.path.dirname(SPEC), '..'))
_ESPEAK_DATA = os.path.join(os.path.dirname(_piper_pkg.__file__), 'espeak-ng-data')
_PLAYWRIGHT_DRIVER = os.path.join(os.path.dirname(_playwright_pkg.__file__), 'driver')

a = Analysis(
    [os.path.join(ROOT, 'kalpavriksha_desktop.py')],
    pathex=[os.path.join(ROOT, 'src')],
    binaries=[],
    datas=[
        (os.path.join(ROOT, 'desktop_app', 'web'), 'web'),
        (os.path.join(ROOT, 'desktop_app', 'voice_models'), 'voice_models'),
        # piper-tts bundles espeak-ng-data as package data; PyInstaller's
        # default collection misses it because it's not imported as a module.
        # Without it, espeakbridge falls back to a hardcoded CI build path.
        (_ESPEAK_DATA, os.path.join('piper', 'espeak-ng-data')),
        # Task 2 — Browser Executive for the founder-objective path.
        # playwright's own Node.js driver is package data PyInstaller's
        # default collection misses the same way it misses espeak-ng-data
        # (not imported as a Python module). The Chromium *browser*
        # binary itself is deliberately NOT bundled here — Playwright
        # resolves it from the machine-level cache
        # (%LOCALAPPDATA%\ms-playwright), the same cache every other
        # Playwright-based process on this machine already shares; a
        # founder without it cached needs `playwright install chromium`
        # once, same as any other Playwright user, not a bundled copy
        # inside this installer.
        (_PLAYWRIGHT_DRIVER, os.path.join('playwright', 'driver')),
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
        'master_agent.desktop.intelligence',
        'master_agent.desktop_operator',
        # Desktop Intelligence's screenshot capability (desktop/intelligence/
        # screenshot.py) imports PIL.ImageGrab lazily, inside a method, not
        # at module scope -- PyInstaller's static analysis does not follow
        # that the same way it already misses pycaw's own COM-based imports
        # above.
        'PIL',
        'PIL.ImageGrab',
        'master_agent.environment_intelligence',
        'master_agent.vigilance',
        'master_agent.memory',
        'sounddevice',
        'faster_whisper',
        'ctranslate2',
        'piper',
        'piper.voice',
        'onnxruntime',
        # C34.4 — live default-device detection (kalpavriksha_desktop.py's
        # _default_input_device_name/_default_output_device_name); COM-
        # based imports PyInstaller's static analysis does not always
        # follow on its own.
        'pycaw',
        'pycaw.pycaw',
        'comtypes',
        'comtypes.stream',
        # Task 2 — Founder Surface -> Planner -> Mission Control -> Browser
        # Executive. `master_agent.launcher` and `master_agent.dashboard`
        # stay excluded below (Dashboard, Persistence, Recovery, the CLI
        # console — none of it used by the minimal composition root
        # `kalpavriksha_desktop.py::_build_mission_pipeline()` builds);
        # only the pieces that composition root actually imports are
        # added here.
        'master_agent.mission_control',
        'master_agent.planner',
        'master_agent.broker',
        'master_agent.ai_infrastructure',
        'master_agent.providers.gemini',
        'master_agent.brain',
        'master_agent.runtime',
        'master_agent.plugins',
        'master_agent.plugins.browser_plugin',
        'master_agent.plugins.registry',
        'master_agent.environment.browser_session',
        'master_agent.executor',
        'master_agent.permissions',
        'playwright',
        'playwright.sync_api',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['master_agent.launcher', 'master_agent.dashboard'],
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
