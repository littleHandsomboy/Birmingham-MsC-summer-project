# Birmingham MSc Summer Project

This repository contains a symbolic task-planning prototype for simplified
electric-motor disassembly.

The current system represents assembly state in structured JSON, grounds
generic disassembly action templates against that state, searches for a valid
action sequence, independently verifies the result, and records state-change
traces. It also supports simulated observation-driven replanning and repeatable
latency benchmarks.

## Current scope

Implemented:

- generic, parameterised disassembly action templates;
- component, connection, tool and robot state representation;
- breadth-first forward planning;
- independent plan replay and verification;
- simulated observation-driven online replanning;
- Markdown and JSON reports;
- automated motor-case and scenario tests;
- a Streamlit interface for running structured cases.

Not currently implemented:

- computer-vision state extraction;
- ROS 2 or physical robot execution;
- Gazebo or URSim visualisation;
- trajectory, force, grasp or contact planning.

The research contribution is the transparent symbolic planning and
verification layer. Robot execution and visualisation remain possible future
integration work.

## Code

The reproducible software project is in [`planning_system/`](planning_system/).
See its [README](planning_system/README.md) for architecture, examples, setup,
tests and commands.

## Demonstration material

- [Gazebo demonstration video](https://drive.google.com/file/d/1EIQfRD4-q2iEfBea3NDFCjjL9H_67tCH/view?usp=drive_link)
