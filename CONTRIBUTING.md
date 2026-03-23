# Contributing to CFA

Thanks for contributing to CFA.

This repository mixes two concerns:

- the **CFA architecture** itself
- the **current Python implementation** of the kernel

Contributions are welcome for both, but it helps to make that distinction explicit in every issue and pull request.

## Before You Start

Please check whether your change is primarily:

- an architecture clarification
- an implementation bug fix
- a new runtime adapter
- a new policy or planner behavior
- a documentation improvement
- a test coverage improvement

When possible, open an issue first for larger changes.

## Development Setup

Requirements:

- Python 3.11+

Install locally:

```bash
pip install -e .[dev]
```

Run tests:

```bash
pytest -q
```

## Contribution Guidelines

### 1. Keep architecture and implementation aligned

If you change runtime behavior that affects the architectural contract, update the relevant documentation:

- [`README.md`](./README.md)
- [`docs/guide.md`](./docs/guide.md)
- the whitepaper files when appropriate

### 2. Prefer explicit contracts

CFA is based on typed contracts, policy evaluation, and state transitions. Avoid introducing opaque behavior that bypasses:

- `StateSignature`
- `PolicyEngine`
- validation stages
- state projection
- audit trail

### 3. Preserve modularity

The repository is intentionally structured so components can be used independently. Try not to couple modules unnecessarily.

### 4. Add tests with behavior changes

If you change:

- policy evaluation
- planning
- code generation
- validation
- execution outcomes
- lifecycle scoring

add or update tests in [`tests`](./tests).

### 5. Prefer small, focused pull requests

PRs are easier to review when they address one concern at a time.

Good examples:

- fix rollback projection semantics
- add a new policy rule
- improve runtime validation contract checks
- add a new execution backend interface

Less ideal:

- refactor kernel, planner, policy, docs, and tests in one unrelated PR

## Pull Request Checklist

Before opening a PR, please confirm:

- tests pass locally
- documentation is updated if needed
- the change is scoped and explained clearly
- architectural impact is described when relevant

## Coding Notes

Some project conventions:

- Python 3.11+
- keep the core types explicit and readable
- prefer deterministic behavior in tests
- treat state and fault modeling as part of the public design

## Discussion Topics That Are Especially Welcome

- state projection semantics
- policy DSL evolution
- context registry design
- lifecycle evidence thresholds
- planner contract design
- safe runtime adapters

## Questions

If something is unclear, open an issue with the shortest reproducible description possible and label whether it is:

- architecture
- implementation
- docs
- question
