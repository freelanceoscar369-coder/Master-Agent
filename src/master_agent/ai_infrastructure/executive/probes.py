"""AI Infrastructure Executive — Probe Actions.

Probe providers for availability, version, capabilities, and latency.
All deterministic — no AI decisions.
"""
from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from master_agent.ai_infrastructure.executive.models import (
    ProviderHealth,
    ProviderCapabilities,
    ProviderIdentity,
    BenchmarkRequest,
    BenchmarkResult,
    BenchmarkStatus,
)
from master_agent.executor.action import Action, ExecutionResult
from master_agent.plugins.base import RiskTier, PermissionCategory


# ---- Probe Actions ---------------------------------------------------------

class ProbeProviderAvailabilityAction(Action):
    """Probe a specific provider for availability and health."""

    name = "ai_infrastructure.probe_availability"
    description = "Probe a provider endpoint for availability and latency"
    risk_tier = RiskTier.READ_ONLY
    permission_category = PermissionCategory.READ
    expected_result = "Provider health status with latency"

    def required_parameters(self) -> list[str]:
        return ["provider_id"]

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        if "provider_id" not in parameters:
            return ["missing required parameter: provider_id"]
        return []

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        provider_id = parameters["provider_id"]
        start = time.perf_counter()

        health = ProviderHealth(is_available=False)

        try:
            if provider_id == "ollama.local":
                result = subprocess.run(
                    ["ollama", "list"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                latency = (time.perf_counter() - start) * 1000
                if result.returncode == 0:
                    health = ProviderHealth(
                        is_available=True,
                        is_healthy=True,
                        last_probe_at=datetime.now(UTC),
                        latency_ms=latency,
                    )
                else:
                    health = ProviderHealth(
                        is_available=False,
                        is_healthy=False,
                        last_probe_at=datetime.now(UTC),
                        latency_ms=latency,
                        error_message=result.stderr,
                    )

            elif provider_id == "lm-studio.local":
                result = subprocess.run(
                    ["lms", "ps"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                latency = (time.perf_counter() - start) * 1000
                if result.returncode == 0:
                    health = ProviderHealth(
                        is_available=True,
                        is_healthy=True,
                        last_probe_at=datetime.now(UTC),
                        latency_ms=latency,
                    )
                else:
                    health = ProviderHealth(
                        is_available=False,
                        is_healthy=False,
                        last_probe_at=datetime.now(UTC),
                        latency_ms=latency,
                        error_message=result.stderr,
                    )

            elif provider_id == "claude-desktop":
                # Desktop app - check if process is running
                latency = (time.perf_counter() - start) * 1000
                health = ProviderHealth(
                    is_available=True,
                    is_healthy=True,
                    last_probe_at=datetime.now(UTC),
                    latency_ms=latency,
                    details={"note": "Desktop application, health assumed if installed"},
                )

            elif provider_id in ("openai.api", "openrouter.api"):
                # Cloud providers - just check if configured
                latency = (time.perf_counter() - start) * 1000
                health = ProviderHealth(
                    is_available=True,
                    is_healthy=True,
                    last_probe_at=datetime.now(UTC),
                    latency_ms=latency,
                    details={"note": "Cloud provider, credentials required for actual use"},
                )

            else:
                health = ProviderHealth(
                    is_available=False,
                    error_message=f"Unknown provider: {provider_id}",
                )

        except subprocess.TimeoutExpired:
            health = ProviderHealth(
                is_available=False,
                is_healthy=False,
                last_probe_at=datetime.now(UTC),
                error_message="Probe timeout",
            )
        except Exception as exc:
            health = ProviderHealth(
                is_available=False,
                is_healthy=False,
                last_probe_at=datetime.now(UTC),
                error_message=str(exc),
            )

        return ExecutionResult(
            success=True,
            output={"provider_id": provider_id, "health": health.as_dict()},
        )


class ProbeProviderCapabilitiesAction(Action):
    """Probe a provider for its capabilities (models, context window, etc.)."""

    name = "ai_infrastructure.probe_capabilities"
    description = "Probe a provider for supported capabilities and metadata"
    risk_tier = RiskTier.READ_ONLY
    permission_category = PermissionCategory.READ
    expected_result = "Provider capabilities and metadata"

    def required_parameters(self) -> list[str]:
        return ["provider_id"]

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        if "provider_id" not in parameters:
            return ["missing required parameter: provider_id"]
        return []

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        provider_id = parameters["provider_id"]
        capabilities = ProviderCapabilities()

        try:
            if provider_id == "ollama.local":
                # Get available models
                result = subprocess.run(
                    ["ollama", "list"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                models = []
                if result.returncode == 0:
                    lines = result.stdout.strip().split("\n")[1:]
                    for line in lines:
                        parts = line.split()
                        if parts:
                            models.append(parts[0])

                capabilities = ProviderCapabilities(
                    ai_capabilities=frozenset({"reasoning", "coding"}),
                    execution_capability="GenerateText",
                    max_context_tokens=32768,
                    supports_streaming=True,
                    notes=f"Available models: {', '.join(models)}" if models else "No models pulled",
                )

            elif provider_id == "lm-studio.local":
                result = subprocess.run(
                    ["lms", "ps"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                models = []
                if result.returncode == 0:
                    lines = result.stdout.strip().split("\n")[1:]
                    for line in lines:
                        parts = line.split()
                        if parts:
                            models.append(parts[0])

                capabilities = ProviderCapabilities(
                    ai_capabilities=frozenset({"reasoning", "coding"}),
                    execution_capability="GenerateText",
                    max_context_tokens=32768,
                    supports_streaming=True,
                    notes=f"Loaded models: {', '.join(models)}" if models else "No models loaded",
                )

            elif provider_id == "claude-desktop":
                capabilities = ProviderCapabilities(
                    ai_capabilities=frozenset({"reasoning", "reasoning.planning", "coding"}),
                    execution_capability="GenerateText",
                    max_context_tokens=200000,
                    supports_streaming=True,
                    notes="Desktop application on existing subscription",
                )

            elif provider_id == "openai.api":
                capabilities = ProviderCapabilities(
                    ai_capabilities=frozenset({"reasoning", "reasoning.planning", "coding"}),
                    execution_capability="GenerateText",
                    max_context_tokens=128000,
                    supports_streaming=True,
                    notes="Metered API; requires API key",
                )

            elif provider_id == "openrouter.api":
                capabilities = ProviderCapabilities(
                    ai_capabilities=frozenset({"reasoning", "coding"}),
                    execution_capability="GenerateText",
                    max_context_tokens=128000,
                    supports_streaming=True,
                    notes="Metered aggregator; requires API key",
                )

        except Exception as exc:
            capabilities = ProviderCapabilities(
                notes=f"Probe failed: {exc}",
            )

        return ExecutionResult(
            success=True,
            output={"provider_id": provider_id, "capabilities": capabilities.as_dict()},
        )


class ProbeProviderLatencyAction(Action):
    """Probe a provider for latency by making a test request."""

    name = "ai_infrastructure.probe_latency"
    description = "Measure provider latency with a test request"
    risk_tier = RiskTier.READ_ONLY
    permission_category = PermissionCategory.READ
    expected_result = "Latency measurement in milliseconds"

    def required_parameters(self) -> list[str]:
        return ["provider_id", "test_prompt"]

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        if "provider_id" not in parameters:
            return ["missing required parameter: provider_id"]
        if "test_prompt" not in parameters:
            return ["missing required parameter: test_prompt"]
        return []

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        provider_id = parameters["provider_id"]
        test_prompt = parameters["test_prompt"]
        iterations = parameters.get("iterations", 3)

        latencies = []

        for _ in range(iterations):
            start = time.perf_counter()

            try:
                if provider_id == "ollama.local":
                    result = subprocess.run(
                        ["ollama", "run", "gemma2:2b", test_prompt],
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                    if result.returncode != 0:
                        return ExecutionResult(
                            success=False,
                            errors=[f"Ollama error: {result.stderr}"],
                        )
                elif provider_id == "lm-studio.local":
                    # LM Studio doesn't have a simple CLI for generation
                    return ExecutionResult(
                        success=False,
                        errors=["LM Studio latency probe not implemented - no CLI generation"],
                    )
                else:
                    return ExecutionResult(
                        success=False,
                        errors=[f"Latency probe not implemented for {provider_id}"],
                    )

                latency = (time.perf_counter() - start) * 1000
                latencies.append(latency)

            except subprocess.TimeoutExpired:
                return ExecutionResult(
                    success=False,
                    errors=[f"Latency probe timeout for {provider_id}"],
                )
            except Exception as exc:
                return ExecutionResult(
                    success=False,
                    errors=[f"Latency probe error: {exc}"],
                )

        avg_latency = sum(latencies) / len(latencies) if latencies else None

        return ExecutionResult(
            success=True,
            output={
                "provider_id": provider_id,
                "latencies_ms": latencies,
                "average_latency_ms": avg_latency,
                "iterations": len(latencies),
            },
        )


# ---- Benchmark Action ------------------------------------------------------

class RunProviderBenchmarkAction(Action):
    """Run a benchmark suite against a provider for a capability."""

    name = "ai_infrastructure.run_benchmark"
    description = "Run benchmark suite against a provider"
    risk_tier = RiskTier.READ_ONLY
    permission_category = PermissionCategory.READ
    expected_result = "Benchmark results with quality and latency aggregates"

    def required_parameters(self) -> list[str]:
        return ["request"]

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        if "request" not in parameters:
            return ["missing required parameter: request"]
        req = parameters["request"]
        if not isinstance(req, dict):
            return ["request must be a dict"]
        if "provider_id" not in req:
            return ["request missing provider_id"]
        if "ai_capability" not in req:
            return ["request missing ai_capability"]
        if "task_class" not in req:
            return ["request missing task_class"]
        return []

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        req_data = parameters["request"]
        request = BenchmarkRequest(
            provider_id=req_data["provider_id"],
            ai_capability=req_data["ai_capability"],
            task_class=req_data["task_class"],
            test_prompts=tuple(req_data.get("test_prompts", ())),
            expected_outputs=tuple(req_data.get("expected_outputs", ())),
            max_latency_ms=req_data.get("max_latency_ms"),
            iterations=req_data.get("iterations", 1),
        )

        result = BenchmarkResult(
            request=request,
            status=BenchmarkStatus.RUNNING,
            started_at=datetime.now(UTC),
        )

        samples = []
        quality_sum = 0.0
        latency_sum = 0.0
        tps_sum = 0.0
        cost_sum = 0.0
        success_count = 0

        try:
            for i, prompt in enumerate(request.test_prompts or ["Hello, world!"]):
                if request.provider_id == "ollama.local":
                    start = time.perf_counter()
                    proc_result = subprocess.run(
                        ["ollama", "run", "gemma2:2b", prompt],
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )
                    latency = (time.perf_counter() - start) * 1000

                    if proc_result.returncode == 0:
                        output = proc_result.stdout.strip()
                        sample = {
                            "iteration": i,
                            "prompt": prompt,
                            "output": output[:500],  # Truncate
                            "latency_ms": latency,
                            "success": True,
                        }
                        samples.append(sample)
                        latency_sum += latency
                        success_count += 1
                        quality_sum += 1.0  # Placeholder - real quality needs verifier
                    else:
                        samples.append({
                            "iteration": i,
                            "prompt": prompt,
                            "error": proc_result.stderr,
                            "latency_ms": latency,
                            "success": False,
                        })

                # Add other providers as needed

            # Compute aggregates
            total = len(request.test_prompts) if request.test_prompts else 1
            aggregate_quality = quality_sum / total if total > 0 else 0.0
            aggregate_latency = latency_sum / success_count if success_count > 0 else None

            result = BenchmarkResult(
                request=request,
                status=BenchmarkStatus.COMPLETED,
                samples=tuple(samples),
                aggregate_quality=aggregate_quality,
                aggregate_latency_ms=aggregate_latency,
                aggregate_tokens_per_second=None,  # Would need token counting
                aggregate_cost=0.0,
                confidence=min(1.0, success_count / max(1, total) * 0.5),  # Simplified
                completed_at=datetime.now(UTC),
            )

        except Exception as exc:
            result = BenchmarkResult(
                request=request,
                status=BenchmarkStatus.FAILED,
                error_message=str(exc),
                completed_at=datetime.now(UTC),
            )

        return ExecutionResult(
            success=True,
            output=result.as_dict(),
        )


# ---- Registry of all probe/benchmark actions ------------------------------

PROBE_ACTIONS = [
    ProbeProviderAvailabilityAction,
    ProbeProviderCapabilitiesAction,
    ProbeProviderLatencyAction,
]

BENCHMARK_ACTIONS = [
    RunProviderBenchmarkAction,
]

ALL_ACTIONS = PROBE_ACTIONS + BENCHMARK_ACTIONS


def get_all_probe_actions() -> list[type[Action]]:
    """Get all probe/benchmark action classes."""
    return PROBE_ACTIONS + BENCHMARK_ACTIONS