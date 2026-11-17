# Project Instructions

- Always use American English spelling, vocabulary, and grammar in all output, including code, comments, docstrings, commit messages, documentation, and chat responses.
- Under `src/`, use explicit relative imports for modules in the same top-level package. Use absolute imports for standard-library and third-party modules and between separate top-level packages such as `pytrain` and `pytrain_ui`.
- After editing Python files, run `../bin/python -m ruff format --check <changed Python files>`.
- If the format check fails, run `../bin/python -m ruff format <changed Python files>` and rerun the format check.
- After making changes, run all unit tests with `../bin/python -m pytest`.
- Always run the tests before declaring a task complete. Do not complete a turn with known failing tests or claim success without a passing full-suite run; fix the cause without weakening assertions, and explicitly report any blocker that prevents verification.
- Run every new or modified test and inspect each new or modified test file with PyCharm inspections, including warnings and weak warnings. Fix all findings before considering the work complete, and review test names, comments, docstrings, and assertion messages for correct American English spelling and grammar. Formatting checks and passing tests do not replace this inspection and language review.
- When a test genuinely requires an inspection-triggering operation, such as accessing a protected member or property, add a narrowly scoped PyCharm suppression comment (for example, `# noinspection PyProtectedMember`) and explain why it is necessary. Use the specific inspection ID; do not disable inspections globally, hide unrelated warnings, or weaken assertions to silence warnings. Rerun inspections after fixes or suppressions, and report any verification that could not be completed.
- Subsystem shutdown must be best effort and must never impede PyTrain shutdown or PyTrainApi handoff; log ordinary cleanup failures and continue remaining teardown. Retain failed cleanup ownership for an explicit retry without gating exit. Genuine `KeyboardInterrupt`/`SystemExit` cancellation must still propagate.
- Subscribe to the most specific available topic in PyTrain (command, action, scope, and address as applicable) so subscribers receive only relevant updates.

- In PyCab Qt, group double-clicks and double-taps by control and elapsed time. Allow the two completed taps anywhere within the same control’s interactive area, with a maximum of 400 ms between them. Check elapsed time explicitly because a busy UI can delay timer delivery. Exclude nested controls from row-body gestures, and cancel pending taps on drags. Preserve the gestures each control supports, including hold-only actions.
- In PyCab Qt, reserve space for a tab scrollbar only when the tab strip overflows. Measure the content gap from the visible bottom edge of the tabs.
