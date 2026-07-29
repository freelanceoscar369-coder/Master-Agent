"""Generic Verification/Evidence/Audit subsystem — see
KALPAVRIKSHA_VISION_V2.md §10 (Verification Philosophy) and
BROWSER_WORKER_ARCHITECTURE.md §3, §8.

Nothing in this package knows about browsers, filesystems, or any other
Environment. It is the shared layer every future Worker's Verifier is
meant to build on — Browser Worker (Mission Brief 022) is its first
concrete consumer, not its only intended one.
"""
