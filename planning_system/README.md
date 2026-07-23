# Generic Disassembly Planning System

Symbolic planning prototype for simplified electric-motor disassembly. The
current implementation uses a structured assembly state and a reusable,
external JSON action library. It supports component-specific action generation,
tool capability and size matching, breadth-first search, independent replay
verification, state-transition traces, and Markdown/JSON reports.

## Current Workflow

```text
Structured Assembly JSON
        +
Generic Action Template Library
        |
        v
Action Grounder
        |
        v
Concrete Grounded Actions
        |
        v
BFS Planner -> Independent Verifier -> Trace / Report
```

The current primary demonstration includes M4 hex end-cover screws, M3 Phillips
bearing-plate screws, two removable components, explicit tool changes, rotor
extraction, and rotor collection.

## What an Action Template Means

An action template is one reusable operation rule. It does not name a specific
motor part. For example, `remove_fastener` states that:

- the selected connection must be an installed and accessible threaded fastener;
- the selected tool must support unscrewing;
- tool thread size and drive type must match the fastener;
- the tool must be mounted before removal;
- the effect changes that fastener connection from `installed` to `removed`.

The action grounder combines this rule with the current state. It can therefore
produce both of these concrete actions from the same template:

```text
remove_fastener[fastener=end_cover_screws,tool=hex_driver_m4]
remove_fastener[fastener=bearing_plate_screws,tool=phillips_driver_m3]
```

## Generic Action Coverage

The external library currently defines:

- `change_tool`
- `inspect_component`
- `remove_fastener`
- `release_retainer`
- `disconnect_connection`
- `debond_joint`
- `cut_connection`
- `remove_component`
- `pull_component`
- `collect_component`

These are high-level symbolic operations. They do not model trajectories,
forces, grasp poses, or physical contact.

## Project Structure

```text
planning_system/
  data/
    generic_disassembly_action_library.json
    case_07_generic_motor_m3_m4.json
    goal_collect_generic_rotor.json
    stream_scenarios/
    test_cases/
  docs/
    project_technical_update.md
  legacy/
  src/planning_system/
    action_template.py
    action_library.py
    action_grounder.py
    observation.py
    online_planner.py
    timing.py
    benchmark.py
    planner.py
    verifier.py
    trace.py
    report.py
  tests/
  outputs/
  app.py
```

The superseded flat Boolean implementation is archived under `legacy/`. It is
not imported or executed by the current system.

A supervisor-facing explanation of the generic action refactoring and
observation-driven replanning is available in
`docs/project_technical_update.md`.

A beginner-oriented Chinese guide covering the complete call flow, stream JSON
fields, all current modules, the three action-system Python files, generic
M3/M4 fastener matching, BFS, verification, and online execution records is
available in `docs/system_guide_zh.md`.

## Run the Generic Motor Case

```bash
cd planning_system
source .venv/bin/activate

python -m planning_system.cli \
  --case data/case_07_generic_motor_m3_m4.json \
  --goal data/goal_collect_generic_rotor.json \
  --action-library data/generic_disassembly_action_library.json \
  --output outputs/case_07_generic_motor_m3_m4_report.md \
  --json-output outputs/case_07_generic_motor_m3_m4_result.json
```

Expected high-level plan:

```text
change M4 tool
-> remove M4 end-cover screws
-> change to gripper
-> remove end cover
-> change M3 tool
-> remove M3 bearing-plate screws
-> change to gripper
-> remove bearing plate
-> change to rotor puller
-> pull rotor
-> change to gripper
-> collect rotor
```

## Run the Incremental Replanning Scenario

```bash
python -m planning_system.online_cli \
  --scenario data/stream_scenarios/motor_stream_01_multilayer_m3_m4.json \
  --output outputs/online/motor_stream_01_multilayer_m3_m4_report.md \
  --json-output outputs/online/motor_stream_01_multilayer_m3_m4_result.json
```

Each stream JSON is self-contained: it stores the initial state, goal, action
library reference and an ordered `observation_stream` array. The loop cursor
consumes one frame per cycle, updates the persistent known state, replans,
verifies the candidate sequence, and applies only the first symbolic action.
It records separate timing for observation loading, state
merge, action grounding, BFS planning, verification, action selection, symbolic
state update, the complete cycle, setup, and the complete experiment. The final
goal is accepted only after a subsequent observation confirms it.

Six directly runnable examples are available under `data/stream_scenarios/`:

- multi-layer M3/M4 motor recovery;
- clip-retained cover;
- prediction/observation conflict;
- missing compatible M4 driver;
- no visible planning frontier;
- adhesive-joint cover followed by rotor recovery.

## Run the Repeated Timing Benchmark

```bash
python -m planning_system.benchmark_cli \
  --scenario data/stream_scenarios/motor_stream_01_multilayer_m3_m4.json \
  --runs 20 \
  --warmups 3 \
  --output outputs/timing/motor_stream_01_timing_benchmark.md \
  --json-output outputs/timing/motor_stream_01_timing_benchmark.json
```

Warm-up runs are excluded. The report includes minimum, mean, median, P95 and
maximum software latency, plus mean and P95 timing for each observation/action
cycle. `expected_action_time_s` remains an action-library estimate and is not a
measurement of physical robot execution.

## Run the UI

```bash
streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

The incremental UI lists the six single-file streams and previews their ordered
frames. Archived multi-file scenarios are kept out of the selector.

## Run Tests

```bash
python -m unittest discover -s tests -v
```

The test suite covers only the current generic action system, including nested
goals, action-library loading, M3/M4 tool compatibility,
retaining constraints, non-fastener connection templates, BFS planning,
verification, trace generation, CLI execution, and batch case execution.
It also covers partial-observation merging, prediction conflicts, final-state
confirmation, per-stage timing and repeated timing benchmarks.

## Run All Cases

```bash
python scripts/run_all_cases.py
```

This runs the current structured cases and writes `outputs/case_summary.md`.

## Run the Ten-Case Motor Test Suite

```bash
python scripts/generate_motor_test_cases.py
python scripts/run_motor_test_cases.py
```

Each generated JSON begins with a `test_case` section explaining the motor
situation, test focus and expected outcome. Individual Markdown/JSON results and
the combined summary are written to `outputs/motor_test_cases/`.

## Scope

This version implements symbolic task planning. The structured JSON is a
planning interface representing currently known assembly information. It is not
yet generated by computer vision. Observation-driven replanning and planning
latency measurement are implemented with simulated symbolic observations. ROS
2 publishing, Gazebo visualisation, physical robot execution and actual visual
recognition are explicitly deferred and are not part of the current test stage.
