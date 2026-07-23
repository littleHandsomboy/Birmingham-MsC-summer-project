"""Repeated timing benchmark for observation-driven planning scenarios."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean, median
from typing import Dict, List, Union

from .online_planner import OnlinePlanningResult, run_online_scenario


@dataclass(frozen=True)
class TimingStatistics:
    """Summary statistics for one latency measurement in milliseconds."""

    count: int
    minimum_ms: float
    mean_ms: float
    median_ms: float
    p95_ms: float
    maximum_ms: float


@dataclass(frozen=True)
class CycleTimingStatistics:
    """Repeated timing statistics for one logical observation cycle."""

    cycle: int
    observation_id: str
    selected_action: str
    planning_ms: TimingStatistics
    cycle_total_ms: TimingStatistics


@dataclass
class OnlineBenchmarkResult:
    """Aggregate and per-run measurements for one online scenario."""

    scenario_name: str
    scenario_path: str
    measured_runs: int
    warmup_runs: int
    successful_runs: int
    setup_ms: TimingStatistics
    total_planning_ms: TimingStatistics
    experiment_total_ms: TimingStatistics
    cycle_statistics: List[CycleTimingStatistics]
    runs: List[Dict[str, object]]

    @property
    def all_runs_successful(self) -> bool:
        return self.successful_runs == self.measured_runs

    def to_dict(self) -> Dict[str, object]:
        payload = asdict(self)
        payload["all_runs_successful"] = self.all_runs_successful
        return payload


def benchmark_online_scenario(
    scenario_path: Union[str, Path], measured_runs: int = 20, warmup_runs: int = 3
) -> OnlineBenchmarkResult:
    """Run a scenario repeatedly and summarise computation latency."""
    if measured_runs < 1:
        raise ValueError("measured_runs must be at least 1.")
    if warmup_runs < 0:
        raise ValueError("warmup_runs cannot be negative.")

    for _ in range(warmup_runs):
        run_online_scenario(scenario_path)

    results = [run_online_scenario(scenario_path) for _ in range(measured_runs)]
    scenario_name = results[0].scenario_name
    cycle_count = len(results[0].cycles)
    if any(len(result.cycles) != cycle_count for result in results):
        raise ValueError("Scenario produced a different cycle count between runs.")

    cycle_statistics = []
    for cycle_index in range(cycle_count):
        reference_cycle = results[0].cycles[cycle_index]
        if any(
            result.cycles[cycle_index].observation_id
            != reference_cycle.observation_id
            or result.cycles[cycle_index].selected_action
            != reference_cycle.selected_action
            for result in results[1:]
        ):
            raise ValueError(
                "Scenario produced a different observation/action sequence "
                "between benchmark runs."
            )
        cycle_statistics.append(
            CycleTimingStatistics(
                cycle=reference_cycle.cycle,
                observation_id=reference_cycle.observation_id,
                selected_action=reference_cycle.selected_action or "no action",
                planning_ms=_summarise(
                    [result.cycles[cycle_index].timing.planning_ms for result in results]
                ),
                cycle_total_ms=_summarise(
                    [
                        result.cycles[cycle_index].timing.cycle_total_ms
                        for result in results
                    ]
                ),
            )
        )

    return OnlineBenchmarkResult(
        scenario_name=scenario_name,
        scenario_path=str(Path(scenario_path).resolve()),
        measured_runs=measured_runs,
        warmup_runs=warmup_runs,
        successful_runs=sum(result.success for result in results),
        setup_ms=_summarise([result.setup_ms for result in results]),
        total_planning_ms=_summarise(
            [result.total_planning_ms for result in results]
        ),
        experiment_total_ms=_summarise(
            [result.experiment_total_ms for result in results]
        ),
        cycle_statistics=cycle_statistics,
        runs=[_run_payload(index, result) for index, result in enumerate(results, 1)],
    )


def generate_benchmark_markdown(result: OnlineBenchmarkResult) -> str:
    """Generate a supervisor-readable timing benchmark report."""
    lines = [
        "# Online Planning Timing Benchmark",
        "",
        "## Configuration",
        "",
        f"- Scenario: `{result.scenario_name}`",
        f"- Warm-up runs excluded from statistics: `{result.warmup_runs}`",
        f"- Measured runs: `{result.measured_runs}`",
        f"- Successful measured runs: `{result.successful_runs}`",
        f"- All measured runs successful: `{result.all_runs_successful}`",
        "",
        "Times below measure software computation latency using the monotonic "
        "high-resolution timer. They do not measure physical robot execution.",
        "",
        "## Overall Timing",
        "",
        "| Metric | Min (ms) | Mean (ms) | Median (ms) | P95 (ms) | Max (ms) |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, statistics in (
        ("Setup", result.setup_ms),
        ("Cumulative BFS planning", result.total_planning_ms),
        ("Complete experiment", result.experiment_total_ms),
    ):
        lines.append(_statistics_row(label, statistics))

    lines.extend(
        [
            "",
            "## Per-Cycle Timing",
            "",
            "| Cycle | Observation | Selected action | Planning mean (ms) | "
            "Planning P95 (ms) | Cycle mean (ms) | Cycle P95 (ms) |",
            "| ---: | --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for cycle in result.cycle_statistics:
        action_name = cycle.selected_action.replace("|", "\\|")
        lines.append(
            f"| {cycle.cycle} | {cycle.observation_id} | "
            f"{action_name} | "
            f"{cycle.planning_ms.mean_ms:.6f} | "
            f"{cycle.planning_ms.p95_ms:.6f} | "
            f"{cycle.cycle_total_ms.mean_ms:.6f} | "
            f"{cycle.cycle_total_ms.p95_ms:.6f} |"
        )
    return "\n".join(lines).strip() + "\n"


def _run_payload(run_number: int, result: OnlinePlanningResult) -> Dict[str, object]:
    return {
        "run": run_number,
        "success": result.success,
        "cycles": len(result.cycles),
        "setup_ms": result.setup_ms,
        "total_planning_ms": result.total_planning_ms,
        "experiment_total_ms": result.experiment_total_ms,
        "cycle_planning_ms": [cycle.timing.planning_ms for cycle in result.cycles],
        "cycle_total_ms": [cycle.timing.cycle_total_ms for cycle in result.cycles],
    }


def _summarise(values: List[float]) -> TimingStatistics:
    ordered = sorted(values)
    return TimingStatistics(
        count=len(ordered),
        minimum_ms=ordered[0],
        mean_ms=mean(ordered),
        median_ms=median(ordered),
        p95_ms=_percentile(ordered, 0.95),
        maximum_ms=ordered[-1],
    )


def _percentile(ordered_values: List[float], fraction: float) -> float:
    if len(ordered_values) == 1:
        return ordered_values[0]
    position = (len(ordered_values) - 1) * fraction
    lower_index = math.floor(position)
    upper_index = math.ceil(position)
    if lower_index == upper_index:
        return ordered_values[lower_index]
    weight = position - lower_index
    return (
        ordered_values[lower_index] * (1.0 - weight)
        + ordered_values[upper_index] * weight
    )


def _statistics_row(label: str, statistics: TimingStatistics) -> str:
    return (
        f"| {label} | {statistics.minimum_ms:.6f} | "
        f"{statistics.mean_ms:.6f} | {statistics.median_ms:.6f} | "
        f"{statistics.p95_ms:.6f} | {statistics.maximum_ms:.6f} |"
    )
