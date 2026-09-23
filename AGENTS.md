# Project Instructions

- Always use American English spelling, vocabulary, and grammar in all output, including code, comments, docstrings, commit messages, documentation, and chat responses.
- After editing Python files, run `../bin/python -m ruff format --check <changed Python files>`.
- If the format check fails, run `../bin/python -m ruff format <changed Python files>` and rerun the format check.
- After making changes, run all unit tests with `../bin/python -m pytest`.
- Subsystem shutdown must be best effort and must never impede PyTrain shutdown or PyTrainApi handoff; log ordinary cleanup failures and continue remaining teardown. Retain failed cleanup ownership for an explicit retry without gating exit. Genuine `KeyboardInterrupt`/`SystemExit` cancellation must still propagate.
