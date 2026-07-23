# models/

Local model weights (e.g. the Hermes checkpoint served by Ollama, or any
other local model files the engine loads at runtime).

Never commit weight files here — see the .gitignore entry for this
folder. This directory exists so there's one obvious place to point
Ollama / a local inference runtime at, and so a fresh machine setup
(see START_HERE.md) has a clear target to download models into.
