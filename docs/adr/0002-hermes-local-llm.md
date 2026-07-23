# ADR-0002: "Hermes integration" = local LLM via Ollama

Status: Accepted (2026-07-23) — confirm default model weight before build

## Context
The Founder Edition feature list names "Hermes integration" alongside
"ChatGPT integration" without further spec. Given the product's
local-first / cloud-enhancement principle, and that Nous Research's Hermes
model family is a well-known open-weight line commonly served locally via
Ollama or LM Studio, the most architecturally coherent reading is: Hermes
is the local-model counterpart to the cloud-hosted ChatGPT integration.

## Decision
Treat "Hermes integration" as: run a Hermes-family open-weight model
locally via Ollama, exposed through the same `ModelProvider` interface as
the ChatGPT plugin (see ARCHITECTURE.md §5). This gives the Model Router a
real local/cloud pair to route between from day one.

## Consequences
- If this reading is wrong — Hermes refers to something else entirely
  (an existing personal tool, a different product) — this ADR needs to be
  revised before the `hermes_provider.py` plugin is built out beyond the
  stub, since the stub currently assumes an OpenAI-compatible local HTTP
  endpoint (Ollama's default).
- Need to confirm: which specific Hermes checkpoint (size/quantization) to
  default to, given the founder's hardware.
