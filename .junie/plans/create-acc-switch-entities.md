---
sessionId: session-260829-224403-1glo
---

# Plan: Speed up GUI launch by fixing filesystem-walking `find_file`

## Requirements

### Overview & Goals

The recent accessory/keypad work made the GUI noticeably slower to launch. Profiling pins the
regression precisely: `pytrain.utils.path_utils.find_file()` performs a full `os.walk` over `.`
**and** `../` on every uncached lookup, and `../` includes the whole virtualenv
(`lib`/site-packages, thousands of files). Measured on this machine:

- ~220 ms per lookup that finds a file, ~950 ms per lookup that misses (walks the entire tree).
- Importing `engine_gui_conf.py` alone costs **~2.4 s**, essentially all of it the 12
  `find_file(...)` calls in the module-level `ENGINE_TYPE_TO_IMAGE` table.
- ~48 `find_file` call sites fire across import + GUI build; the Steam Deck builds two
  `EngineGui` panes, doubling the build-time share.

The goal is to cut launch time by making file resolution cheap, without changing which files
get resolved. Per the confirmed direction, the primary fix is to **index each search root once
and serve later lookups from that cache, while pruning the virtualenv and build/dot dirs out of
the walk**. Three smaller startup speedups ride along.

### Scope

**In Scope**

- Rework `find_file` (and its sibling `find_dir`) in `src/pytrain/utils/path_utils.py` to walk
  each search root at most once into a cached filename->paths index, and to skip the
  virtualenv/site-packages and dot/build directories while walking.
- Preserve current lookup semantics: same inputs resolve to the same path (including the
  existing first-match-wins ordering and the `Path`-that-exists short-circuit).
- Remove the leftover debug `print(f"{source} scaled to ...")` in
  `GuiZeroBase.get_scaled_image` (`guizero_base.py`).
- Make module-level `find_file` tables lazy so path resolution moves off the import critical
  path -- primarily `ENGINE_TYPE_TO_IMAGE` in `engine_gui_conf.py`, plus the other eager
  module-level `find_file(...)` tables reached during launch.
- Defer icon decoding for keypad cells that start hidden, so `Image.open`/`resize`/
  `ImageTk.PhotoImage` runs when a panel is first shown rather than during `build`.

**Out of Scope**

- Any change to the accessory/keypad *features* (BPC2/ASC2/Sensor Track/AMC2 behavior, panel
  toggles, provisional creation, naming) -- purely a performance pass.
- Re-architecting the image cache or `guizero`/Tk internals beyond the `print` removal and the
  lazy-decode deferral.
- Bundling assets differently or moving image files.
- Changing CLI `find_file` uses that run outside GUI launch (e.g. `make_gui.py`,
  `make_service.py`) except as they benefit for free from the faster `find_file`.

### User Stories

1. As an operator launching the controller, I want the window to appear quickly, so I am not
   waiting several seconds of filesystem scanning before I can drive trains.
2. As a developer, I want file resolution to be O(1) after a one-time index, so adding more
   bundled images/icons does not keep inflating startup time.

### Non-Functional Requirements

- **NFR-1 (correctness)** Every `find_file` / `find_dir` input that resolves today resolves to
  the same path afterward; misses still return `None`. Locked by tests.
- **NFR-2 (speed)** Total `find_file` cost during a cold launch drops from ~48 full tree walks
  to at most one walk per distinct search root; the `ENGINE_TYPE_TO_IMAGE` import cost
  (~2.4 s) is removed from the import path.
- **NFR-3 (safety)** No behavior change for GUI features; the full `pytest` suite stays green
  and `ruff format --check` is clean.
- **NFR-4 (parity)** Identical on Portrait and both Steam Deck panes.

## Technical Design

### Current Implementation

**The hot path** -- `src/pytrain/utils/path_utils.py`:

```python
@lru_cache(maxsize=2048)
def find_file(target: str | Path, places: Tuple = (".", "../")) -> str | None:
    name, concrete = _normalize_target(target)
    if concrete and concrete.is_file():
        return str(concrete)
    for d in places:
        if not os.path.isdir(d):
            continue
        for root, _, files in os.walk(d):          # <-- walks the whole tree, every call
            if root.startswith("./.") or root.startswith("./venv/"):
                continue
            root_path = Path(root).resolve()
            parts = root_path.parts
            if any(p.startswith(".") or p in EXCLUDE for p in parts):
                continue
            for file in files:
                if file.startswith(".") or file in EXCLUDE:
                    continue
                if file == name:
                    return str(root_path / file)
    return None
```

`@lru_cache` only helps *repeat* lookups of the *same* target; each distinct file still walks
the tree from scratch. The default `places=(".", "../")` means every miss also walks `../`,
which for a typical install is the environment root containing `bin/` and `lib/pythonX/
site-packages/` -- tens of thousands of files. `EXCLUDE` already lists `venv`, `.tox`, `.git`,
etc., but the venv here is not named `venv` (it is the parent env's `lib`), so it is not pruned.

**The import-time amplifier** -- `engine_gui_conf.py:538-551`:

```python
ENGINE_TYPE_TO_IMAGE = {
    EngineType.ACELA: find_file("acela.jpg"),
    ...  # 12 entries, each a full tree walk at import time
}
```

`engine_gui_conf` is imported transitively by `guizero_base` -> `accessory_base` -> the whole
controller stack, so these 12 walks run before the window is built. Import profiling
(`python -X importtime`) attributes ~2.39 s of *self* time to `engine_gui_conf`.

**Other eager `find_file` tables reached during launch** include
`accessory_base._common_button_image_paths()` (6 lookups) and the per-cell `find_file(...)`
calls throughout `KeypadView.build` (each keypad image, including cells that start hidden).

**The leftover debug print** -- `guizero_base.py` `get_scaled_image`:

```python
print(f"{source} scaled to {scaled_width}x{scaled_height} = {orig_width}x{orig_height}")
```

Synchronous stdout I/O on the Tk thread, once per scaled image.

**Synchronous decode at build** -- `_build_keypad_button` (`guizero_base.py:675-677`) calls
`self.get_titled_image(image)` immediately for any button given an `image`, decoding it even
for cells created `visible=False`.

### Key Decisions

| Decision | Choice | Rationale |
| --- | --- | --- |
| `find_file` strategy | **Index once, then prune** (user-confirmed) | Walk each search root at most once into a cached `{filename: [paths]}` index; serve later lookups from it. Same search semantics, but ~48 walks collapse to one per root. Also prune the virtualenv/site-packages and dot/build dirs so even that one walk is cheap. |
| Ordering / first-match semantics | Preserve exactly | The index records paths in walk order per search root and per `places` tuple, so "first match wins" is unchanged and existing callers keep resolving to the same file. |
| `Path`-that-exists short-circuit | Keep as-is | `_normalize_target` still returns early for a concrete existing path before consulting the index. |
| Cache invalidation | Index is process-lifetime, keyed by resolved search-root set | Bundled assets do not appear/disappear mid-run; `prod_info.py` cache-dir lookups that expect freshness keep passing explicit `places` and can opt out of the index (see Risks). |
| Lazy `ENGINE_TYPE_TO_IMAGE` | Resolve on first access, not at import | Moves ~2.4 s off the import path; a module-level mapping backed by a cached resolver (dict subclass or `functools.cache` accessor) keeps call sites unchanged. |
| Deferred icon decode | Decode hidden keypad cells lazily on first `show()` | Avoids decoding icons the entry screen never displays; visible cells still decode during build so the first frame is complete. |
| `print` removal | Delete outright | Pure debug leftover; no replacement needed (module already uses `log`). |

### Proposed Changes

**1. `path_utils.py` -- index-and-prune `find_file` / `find_dir`.**

- Add a module-level cache mapping a normalized `places` key -> an index built by walking each
  root once: `{basename: [full_path, ...]}` in walk order, applying the existing dot/`EXCLUDE`
  pruning **plus** virtualenv/site-packages pruning (e.g. skip any directory named
  `site-packages`, `lib`, `bin`, `include`, or matching the active `sys.prefix` /
  `VIRTUAL_ENV`).
- `find_file(target, places)` becomes: normalize -> concrete short-circuit -> build/fetch the
  index for `places` -> return the first indexed path for `basename` (or `None`).
- `find_dir` gets the analogous directory index.
- Keep the public signatures and return types identical; keep `@lru_cache` on the thin
  wrapper (or replace with the index lookup, which is already memoized).
- Add an internal `reset_index()`/cache-clear used by tests.

**2. `engine_gui_conf.py` -- make `ENGINE_TYPE_TO_IMAGE` lazy.**

- Replace the eager dict literal of `find_file(...)` values with a lazy resolver keyed by
  `EngineType` (e.g. a small mapping of `EngineType -> filename` plus a cached
  `image_for_engine_type(t)` accessor, or a `dict`-like that resolves on `__getitem__`).
- Update the (few) readers of `ENGINE_TYPE_TO_IMAGE` to go through the accessor.
- Give the same treatment to any other module-level `find_file` table on the launch path
  (audit `accessory_base._common_button_image_paths`, `engine_gui.py`,
  `controller_view.py`) -- prefer resolving on first use.

**3. `guizero_base.py` -- remove the debug print; defer hidden-cell decode.**

- Delete the `print(...)` line in `get_scaled_image`.
- In `_build_keypad_button`, when a button is created `visible=False`, store the image name but
  skip `get_titled_image(...)`; decode lazily the first time the cell is shown (e.g. a small
  hook on the cell/`show()` path, or a deferred `after_idle` decode) so the icon is present
  when the panel first appears. Visible-at-build cells keep decoding eagerly.

### Data Models / Contracts

```python

# path_utils.py

def find_file(target: str | Path, places: Tuple = (".", "../")) -> str | None   # unchanged signature
def find_dir(target: str | Path, places: Tuple = (".", "../")) -> str | None    # unchanged signature
def _index_for(places: Tuple[str, ...]) -> dict[str, list[str]]                 # new, internal, cached
def reset_path_index() -> None                                                  # new, test hook

# engine_gui_conf.py

def image_for_engine_type(engine_type: EngineType) -> str | None               # lazy resolver (or dict-like)
```

### Architecture Diagram

```mermaid
graph TD
    subgraph Before
        A1[find_file call #1] --> W1[os.walk . and ../ incl. venv]
        A2[find_file call #2] --> W2[os.walk . and ../ incl. venv]
        A3[find_file call N] --> W3[os.walk . and ../ incl. venv]
    end
    subgraph After
        B1[find_file call #1] --> IDX{index for places}
        B2[find_file call #2] --> IDX
        B3[find_file call N] --> IDX
        IDX -->|first call, miss| WALK[walk each root once, prune venv/dot/build]
        WALK --> IDX
        IDX --> P[return path]
    end
    LAZY[ENGINE_TYPE_TO_IMAGE lazy] -.moves 2.4s off import.-> B1
    DEFER[hidden keypad cells decode on show] -.less decode at build.-> P
```

### Components / Files

| File | Change |
| --- | --- |
| `src/pytrain/utils/path_utils.py` | Index-and-prune `find_file`/`find_dir`; add `_index_for`, venv/site-packages pruning, and a test-only `reset_path_index()` |
| `src/pytrain/gui/controller/engine_gui_conf.py` | Make `ENGINE_TYPE_TO_IMAGE` lazy via an `image_for_engine_type(...)` accessor |
| `src/pytrain/gui/guizero_base.py` | Remove the debug `print` in `get_scaled_image`; defer decode for `visible=False` keypad cells in `_build_keypad_button` |
| `src/pytrain/gui/controller/keypad_view.py` | Adjust to the deferred-decode path if a `show()` hook is needed for hidden image cells |
| `src/pytrain/gui/accessories/accessory_base.py` | Audit/lazy-ify `_common_button_image_paths()` if it is on the import/launch path |
| `tests/utils/` (new/updated) | Lock `find_file`/`find_dir` correctness and one-walk behavior |
| `tests/gui/` | Assert the print is gone and hidden-cell icons still render on first show; keep parity suites green |

### Risks

| Risk | Mitigation |
| --- | --- |
| Indexed lookups change which path wins vs. today | Build the index in the same walk/prune order as the current loop and return the first match; add tests that resolve a set of known files before/after and compare |
| Cache-dir lookups (`prod_info.py`) that expect freshly written files miss the index | Those calls pass explicit `places` (cwd + cache dir); keep an opt-out (bypass the process-lifetime index for non-default `places`, or expose `use_index=False`) so newly written cache files are still found |
| Over-aggressive venv pruning skips a legitimately-bundled file living under a pruned dir name | Prune by resolved path against `sys.prefix`/`VIRTUAL_ENV` and known env subdirs rather than by bare name where feasible; cover with a test that a real bundled asset still resolves |
| Deferred decode leaves a blank icon on first show | Decode on the cell's first `show()` (or `after_idle` right after) so the icon is present when the panel first renders; test that a hidden->shown cell has its image set |
| Lazy `ENGINE_TYPE_TO_IMAGE` breaks a caller expecting a plain dict | Provide a dict-like/accessor with the same read API and update the handful of readers |
| Behavior regressions in accessory features | This is a perf-only pass; rely on the full existing GUI suite (2106 tests) staying green |

## Testing

### Validation Approach

- **`find_file` correctness & speed** -- headless unit tests in `tests/` that build a temp
  directory tree, assert `find_file`/`find_dir` return the same paths as a reference walk, and
  assert the underlying `os.walk` runs **once per search root** across many lookups (e.g. patch
  `os.walk` with a counting wrapper). Include a miss case and the concrete-`Path` short-circuit.
- **Import cost** -- a test (or a documented `python -X importtime` check) confirming
  `engine_gui_conf` no longer resolves image paths at import (e.g. importing it does not call
  `find_file`; patch/spy `find_file` and assert zero calls at import).
- **GUI parity** -- the existing headless suites (`test_keypad_view.py`,
  `test_gui_deck_parity.py`, `test_gui_checkpoint.py`, accessory suites) stay green, proving no
  feature regression on Portrait or the Steam Deck panes.

### Key Scenarios

- Resolving the 12 `ENGINE_TYPE_TO_IMAGE` files, the 6 common button images, and a handful of
  keypad icons yields the same paths as before, with a single walk per root.
- A missing filename returns `None` (and does not trigger a second full walk on the next miss).
- `get_scaled_image` produces the same `PhotoImage` with no stdout output.
- A keypad cell created hidden has no decoded image until first shown; after `show()` its image
  is set and correct (visible-at-build cells are unaffected).

### Edge Cases

- Non-default `places` (e.g. cache-dir lookups in `prod_info.py`) still find freshly written
  files -- covered by the index opt-out.
- A file that exists in more than one search root resolves to the same one as today
  (first-match order preserved).
- Compact (`_compact=True`) / pane-hosted construction: deferred decode and parity hold.
- Running from a project checkout vs. an installed package (different `.`/`../` layouts) both
  resolve bundled assets.

### Test Changes

- **Add** `tests/utils/test_path_utils.py` (or extend existing): correctness parity, single-walk
  assertion, miss handling, `Path` short-circuit, index reset, non-default `places` opt-out.
- **Add** an import-cost guard that `find_file` is not called while importing
  `engine_gui_conf`.
- **Add/extend** a GUI test that a hidden keypad image cell decodes on first show.
- **Verify unchanged** the accessory/keypad/parity/checkpoint suites.

## Delivery Steps

### Stage 1: Index-and-prune `find_file` / `find_dir`

`find_file` and `find_dir` walk each search root at most once into a cached index and serve all
later lookups from it, with the virtualenv/site-packages and dot/build dirs pruned, and
identical resolution results.

- In `src/pytrain/utils/path_utils.py`, add `_index_for(places)` that walks each root once into
  `{basename: [full_path, ...]}` in current walk order, applying the existing dot/`EXCLUDE`
  pruning plus virtualenv/site-packages pruning (skip dirs matching `sys.prefix`/`VIRTUAL_ENV`
  and known env subdirs like `site-packages`, `lib`, `bin`, `include`).
- Rewrite `find_file`/`find_dir` to normalize, honor the concrete-`Path` short-circuit, then
  return the first indexed match (or `None`), preserving first-match-wins ordering.
- Provide an index opt-out (or bypass for non-default `places`) so `prod_info.py`'s cache-dir
  lookups still see freshly written files.
- Add `reset_path_index()` for tests.
- Add `tests/utils/test_path_utils.py`: resolution parity against a reference walk, a
  single-walk assertion via a counting `os.walk` wrapper, miss handling, the `Path`
  short-circuit, and the non-default-`places` opt-out.
- Run `../bin/python -m ruff format --check` on the changed files and
  `../bin/python -m pytest` for the affected suites.

### Stage 2: Move image-path resolution off the import path (lazy `ENGINE_TYPE_TO_IMAGE`)

Importing `engine_gui_conf` no longer resolves any image paths, removing the ~2.4 s of
import-time `find_file` walks from launch.

- In `engine_gui_conf.py`, replace the eager `ENGINE_TYPE_TO_IMAGE` dict of `find_file(...)`
  values with a lazy resolver (`image_for_engine_type(engine_type)` backed by
  `functools.cache`, or a dict-like that resolves on `__getitem__`) over a plain
  `EngineType -> filename` mapping.
- Update the readers of `ENGINE_TYPE_TO_IMAGE` to use the accessor.
- Audit and lazy-ify other module-level `find_file` tables on the launch path
  (`accessory_base._common_button_image_paths`, and any in `engine_gui.py` /
  `controller_view.py`) so resolution happens on first use.
- Add an import-cost guard test asserting `find_file` is not called while importing
  `engine_gui_conf`.
- Run `../bin/python -m ruff format --check` on the changed files and `../bin/python -m pytest`.

### Stage 3: Trim synchronous startup work in `guizero_base` and finish the pass

The leftover debug print is gone and hidden keypad icons decode lazily on first show, further
shrinking the work done before the first frame; the full suite is green on Portrait and both
Steam Deck panes.

- In `guizero_base.py`, delete the `print(f"{source} scaled to ...")` line in
  `get_scaled_image`.
- In `_build_keypad_button`, for `visible=False` image cells, store the image name and skip the
  eager `get_titled_image(...)`; decode on the cell's first `show()` (or an `after_idle`
  immediately after) so the icon is present when the panel first renders. Keep visible-at-build
  cells decoding eagerly; wire any needed `show()` hook in `keypad_view.py`.
- Add a GUI test that a hidden keypad image cell has no decoded image until shown, then has the
  correct image after `show()`; assert `get_scaled_image` emits no stdout.
- Confirm the accessory/keypad/parity/checkpoint suites are unchanged.
- Run `../bin/python -m ruff format --check` on all changed Python files, fix with
  `ruff format` if needed, then run the full `../bin/python -m pytest`.

<!-- ============================================================================= -->
<!-- The content below is stale orchestrator briefing / session history and is NOT -->
<!-- part of the plan. It is retained only because those lines are not editable.   -->
<!-- ============================================================================= -->

# Delivery Steps

### ✓ Step 1: Implementation
<plan_session_history>
History processor: During the current session, you have worked on the following `<previous_issue>`.
The `<issue_description>` usually continues or extends your previous work. Consider all `<previous_issue>` and `<issue_description>` together.
If `<assistant_question>`/`<user_answer>` blocks are present, treat them as additional user-provided context that may contain important clarifications about the task.
<previous_issue>
## Plan Task
Both the Portrait and Landscape controllers are now very well equiped to operate my layout. Thank you. But in addition to operating trains, I want to use the graphical controllers to add new engines, configure LCS modules, and name new switches and accessories. Currently, EngineGui only allows you to select existing entities. If you enter an Accessory number that doesn't exist, the Gui doesn't leave the Entry screen. This is also True for Engines, Routes, Trains, and Switches. 

I need a plan to allow Accessories, Switches, and Engines to be created as well as edited. Trains and Routes will not be considered at this time, as those GUIs are much more complicated (Trains are made from one or more engines, routes are made from one or more switches and routes). 

Accessories are again a special case. BPC2 and ASC2 consume a block of TMCC IDs (addresses), and PyTrain already allows me to edit their name and road numbers by long pressing on the image above the keypad and then using the EditableText widgets on the StateInfoPanel displayed. But These screens also need to be able to toggle the native Acc operating screen (the one with the throttle, coupler keys, and most importantly, the Set Address button). I need a button added to their operating screen that allows toggling to the generic Acc panel, and then on the Acc panel, to get back to the LCS-specific display. 

I also need the Gui modified so that if I select an accessory that isn't defined nor backed by an LCS device, it displays the generic Acc panel. That panel has the functionality to configure a new LCS device. But it also needs to have an "Info" key added to it (preferably in the 4th column) that will display the StateInfoPanel for this TMCC ID and allow me to assign a Name and Road Number to the new Accessory.

I need something similar for Switches as well. We will do Engines in another turn.

Please confirm you understand my request and develop an implementation plan. CHeckpoint the current state of the GUI so we can catch regressions. These features need to be implemented on both the Landscape and Portrait displays, so I am thinking you should focus on EngineGui. SteamDeckGui should be able to reuse that capability directly.

What else do you need from me to proceed?
</previous_issue>
<assistant_question>
I have a clear picture of the mechanics now. Let me confirm a few behavioral choices with you.
tool name: ask_user
tool parameters:
 - "questions"=[{"name":"Create Trigger","question":"When you type a TMCC ID that doesn't exist yet and press ↵ (Enter) in Accessory/Switch/Engine scope, what should happen?","options":[{"title":"Create then show info","description":"Materialize the record, go straight to the operating screen, and pop the StateInfoPanel so you can type a Road Name immediately — this is exactly what the `Set` key already does today in `keypad_view.on_keypress`."},{"title":"Create, no popup","description":"Materialize the record and go to the operating screen only; you reach naming yourself via the new Info key or a long-press on the image."},{"title":"Confirm first","description":"Show a small \"Create Accessory 14?\" confirmation popup before creating anything, guarding against a mistyped ID."}],"allowMultiple":false},{"name":"Info Key Placement","question":"Which operating screens should get the new \"Info\" key that opens the StateInfoPanel for the current TMCC ID?","options":[{"title":"Generic Acc + Switch","description":"The two screens you named — the generic Accessory panel (4th column, using the free grid slot at column 3 / row 2) and the Switch operating screen, which today has no image and therefore no long-press route to the info panel at all."},{"title":"All accessory panels","description":"Also add it to the BPC2, ASC2, Sensor Track and AMC2 panels so naming is reachable the same way everywhere, not only by long-pressing the image."},{"title":"Route screen too","description":"Include the Route operating screen for consistency, even though route creation itself stays out of scope."}],"allowMultiple":true},{"name":"Panel Toggle Reach","question":"Which LCS-specific screens should get the button that toggles to the generic Accessory panel (with `Set Address`, throttle, coupler keys) and back?","options":[{"title":"BPC2 and ASC2","description":"The screens you called out; the ASC2 already carries a similar toggle button (`ac_op_btn`) to the configured-accessory view, so this sits beside it."},{"title":"Also Sensor Track","description":"Sensor Track replaces the whole keypad with the Sequence list, so it needs the toggle placed in its own box rather than in a keypad cell."},{"title":"Also AMC2","description":"AMC2 likewise replaces the keypad with its own ops panel and would need the toggle inside `Amc2OpsPanel`."}],"allowMultiple":true}]
</assistant_question>
<user_answer>
### Response for the question "Create Trigger"
Free text response: Lets focus on Accessories and switches first. It should display the generic operating screen augmented with a Set button and an Info button (if ones do not exist). The Info button should display the StateInfoPanel where the user can define a Road Number and Name.

### Response for the question "Info Key Placement"
Selected options: Generic Acc + Switch

### Response for the question "Panel Toggle Reach"
Selected options: BPC2 and ASC2, Also Sensor Track, Also AMC2
</user_answer>
<assistant_question>
<UPDATE>
<PREVIOUS_STEP>`ComponentStateStore.get_state(create=True)` materializes a state via a defaultdict-style `ComponentStateDict`, so it becomes a real, queryable store entry; `CompDataMixin.initialize` (comp_data.py:246) builds `AccessoryData`/`SwitchData` with `_empty=True` and `_comp_data_record=True`, so `is_comp_data_empty` stays True until the Base 3 answers. That's the exact primitive the existing `Set`-key path uses, so Enter-on-unknown-ID can reuse it verbatim. Column 3 of the keypad grid has a free slot at row 2 (SET=[3,0], toggle=[3,1], Aux1=[3,3], Aux2=[3,4]) — the natural home for the new Info key in the 4th column.</PREVIOUS_STEP>
<EXTERNAL>Confirmed the creation primitive: asking the state store for a missing ID with creation enabled plus `comp_data.initialize` gives a live, editable record whose comp-data still reads as "empty" until the Base 3 replies — precisely what the `Set` key already does, so Enter can share it. I also found the 4th keypad column has an unused slot at row 2, which is exactly where your Info key can go without disturbing Set, Toggle, Aux1 or Aux2. Now I want to settle one structural question with you — where the "which accessory panel am I showing" override should live — because that single decision point also drives the Steam Deck gamepad bindings.</EXTERNAL>
</UPDATE>
tool name: ask_user
tool parameters:
 - "questions"=[{"name":"Panel Override Location","question":"Today `KeypadView.accessory_panel_kind` is the single place that decides which accessory panel is drawn, and the Steam Deck input layer reads the same property to pick its gamepad bindings. Where should the new \"show the generic panel instead\" override live?","options":[{"title":"Per-ID override map on EngineGui","description":"`EngineGui` keeps a `{tmcc_id: panel_kind}` map that `_panel_kind_for` consults first; the toggle writes into it, so each device remembers which face you left it on and the pad follows automatically.\n```mermaid\ngraph LR\n  T[Toggle key] --> M[EngineGui override map]\n  M --> K[panel_kind_for]\n  K --> U[Panel drawn]\n  K --> P[Gamepad context]\n```"},{"title":"Single transient flag on KeypadView","description":"One `_forced_panel_kind` field cleared on every selection change; simpler, but the toggle resets whenever you leave and come back to the device.\n```mermaid\ngraph LR\n  T[Toggle key] --> F[KeypadView flag]\n  F --> K[panel_kind_for]\n  K --> U[Panel drawn]\n  K --> P[Gamepad context]\n```"},{"title":"Separate resolver module","description":"A new `accessory_panel_resolver.py` owning both the state-flag rules and the overrides, with `KeypadView` delegating to it; cleanest separation but moves well-tested logic.\n```mermaid\ngraph LR\n  T[Toggle key] --> R[Panel resolver]\n  S[Acc state flags] --> R\n  R --> U[Panel drawn]\n  R --> P[Gamepad context]\n```"}],"allowMultiple":false},{"name":"Undefined ID Persistence","question":"When you Enter an undefined Accessory/Switch ID and get the augmented generic screen, should the new record be pushed onto the recents list and scope catalog right away, or only once you give it a Road Name?","options":[{"title":"Only after naming","description":"Keep the provisional record out of the header dropdown and catalog until a Road Name or Road Number is committed, so mistyped IDs leave no litter behind."},{"title":"Immediately on Enter","description":"Treat it like any other selection — it appears in recents at once, consistent with how `make_recent` works for existing components today."}],"allowMultiple":false},{"name":"Checkpoint Form","question":"For the regression checkpoint of the current GUI, what would you like?","options":[{"title":"Behavior-locking test module","description":"A new headless test module (in the style of `tests/gui/test_engine_gui_transitions.py`) that asserts today's panel selection, keypad cell visibility and entry/ops transitions for every scope, committed before any behavior changes."},{"title":"Tests plus a written baseline doc","description":"The same tests, plus a short document under `doc/` describing the current screens per scope, so a human can eyeball what changed."},{"title":"Rely on existing suites","description":"Skip a dedicated checkpoint and lean on the existing keypad/accessory/transition suites, extending them as the work proceeds."}],"allowMultiple":false}]
</assistant_question>
<user_answer>
### Response for the question "Panel Override Location"
Selected options: Single transient flag on KeypadView

### Response for the question "Undefined ID Persistence"
Selected options: Only after naming

### Response for the question "Checkpoint Form"
Selected options: Behavior-locking test module
</user_answer>
<previous_issue_solution>
I have everything I need. Here's the plan.
tool name: submit
tool parameters:
 - "name"="create-acc-switch-entities",
 - "proposal"=[{"name":"Requirements","content":"### Overview & Goals\n\nToday `EngineGui` is a *selector* for entities that already exist. Typing a TMCC ID that the Base 3 has never heard of leaves you stranded on the entry keypad: `KeypadView.on_keypress`'s `↵` branch calls `EngineGui.make_recent`, gets `False` because `state_store.get_state(..., create=False)` returned nothing, and falls straight back to `entry_mode`.\n\nThis change makes the graphical controllers able to **create** as well as operate **Accessories** and **Switches**, and makes the LCS-specific accessory screens (BPC2, ASC2, Sensor Track, AMC2) able to toggle to the generic Accessory screen — the one that carries `Set Address` — and back.\n\nPer your direction, **Engines, Trains and Routes are out of scope** for this pass.\n\n### Scope\n\n**In Scope**\n\n- `↵` on an undefined **Accessory** or **Switch** ID enters the operating screen instead of bouncing back to entry.\n- That screen is the **generic** panel for its scope, augmented with a `Set` key and an `Info` key where those do not already exist.\n- `Info` opens the existing `StateInfoOverlay` for the current TMCC ID, where Road Name and Road Number can be assigned.\n- A provisional (unnamed) record stays out of the recents dropdown and the scope catalog until a Road Name or Road Number is committed.\n- A **panel toggle** on the BPC2, ASC2, Sensor Track and AMC2 operating screens that switches to the generic Accessory panel, and a way back from the generic panel to the LCS-specific one.\n- Everything works identically on the portrait controller and on both Steam Deck panes, because it all lands in `EngineGui` / `KeypadView`, which `SteamDeckGui` hosts unchanged.\n- A behavior-locking checkpoint test module committed **before** any behavior change.\n\n**Out of Scope**\n\n- Engine and Train creation (deferred to a later turn, as you asked).\n- Route creation and Route editing.\n- Creating or editing `accessory_config.json` entries (configured accessories) from the GUI — naming here writes Road Name/Road Number to the Base 3 via `comp_data`, exactly as long-pressing the image does today.\n- New gamepad bindings for the new keys; the existing context chains keep working because they are keyed off the reported panel kind.\n\n### User Stories\n\n1. As an operator, I want to key in an Accessory number that does not exist yet and press `↵`, so that I land on the generic Accessory screen and can press `Set` to program a new LCS device or accessory to that address.\n2. As an operator, I want an `Info` key on that screen, so that I can give the new Accessory a Road Name and Road Number without hunting for a long-press target.\n3. As an operator, I want the same for an undefined Switch number, so that I can name new switches — today the Switch screen has no image at all, so long-press info is simply unavailable there.\n4. As an operator on a BPC2 or ASC2 screen, I want a key that takes me to the generic Accessory panel so I can reach `Set Address`, and a key there that takes me back to the LCS-specific display.\n5. As an operator, I do not want mistyped IDs cluttering my recents list or scope catalog.\n\n### Functional Requirements\n\n**FR-1 — Create on `↵`**\n\n- Scope is `ACC` or `SWITCH`, entered ID passes the same validation the `Set` key already applies (`2 <= id <= 98`, `id != 99`), and no state exists → materialize the record and enter ops mode.\n- Scope is `ENGINE`, `TRAIN` or `ROUTE` → unchanged; still returns to entry mode.\n- An out-of-range or `0` ID → unchanged; still returns to entry mode.\n\n**FR-2 — Augmented operating screen**\n\n| Screen | `Set` | `Info` |\n| --- | --- | --- |\n| Generic Accessory | already present (aux cell, `SET_ADDRESS`) | **new**, 4th column |\n| Switch | **new** | **new**, 4th column |\n\n- `Info` opens `StateInfoOverlay` for the current scope + TMCC ID with Road Name and Road Number editable, and `Clear` disabled for LCS-backed states (`LcsState.is_deletable` is already `False`).\n- Both keys appear for provisional *and* already-defined Accessories/Switches — you asked for creation *and* editing.\n\n**FR-3 — Deferred promotion**\n\n- A provisional record does not appear in the header `Combo`, the recents deque, or the `CatalogPanel` list.\n- Committing a Road Name or Road Number promotes it: it is added to recents, the options list is rebuilt, and the catalog cache is reset.\n- A real configuration record arriving from the Base 3 for that ID promotes it too.\n- Leaving the ID without naming it leaves no trace in recents or the catalog.\n\n**FR-4 — Panel toggling**\n\n- BPC2, ASC2, Sensor Track and AMC2 screens each carry a key that switches the display to the generic Accessory panel for the same TMCC ID.\n- The generic panel, when reached that way, carries a key back to the LCS-specific panel.\n- An Accessory ID that is neither defined nor backed by an LCS device displays the generic panel — which is already what the panel-kind rules produce; the fix is being able to *reach* ops mode at all (FR-1).\n- The gamepad follows the screen: because `KeypadView.accessory_panel_kind` remains the single decision point, a forced-generic display reports `generic` and the input layer picks the `acc_generic` chain automatically.\n\n**FR-5 — Override lifetime**\n\nPer your choice, the override is a **single transient flag**: it is cleared on any change of selected TMCC ID, any change of scope, and on return to entry mode. Leaving a device and coming back shows its native panel again.\n\n### Non-Functional Requirements\n\n- No geometry regressions on the compact (Steam Deck) panes: new keys occupy existing empty grid slots and add no rows or columns.\n- No new blocking work on the Tk thread; naming continues to go out through `BaseReq.process_sync_reqs(..., do_async=True)`.\n- `ruff format --check` clean; full `pytest` suite green."},{"name":"Technical Design","content":"### Current Implementation\n\n**The dead end.** `KeypadView.on_keypress` (`keypad_view.py:590`):\n\n```python\nelif key == ENTER_KEY:\n    self._reset_on_keystroke = False\n    if host.make_recent(host.scope, int(tmcc_id)):\n        host.ops_mode()\n    else:\n        self.entry_mode(clear_info=False)   # <-- the trap\n```\n\n`EngineGui.make_recent` returns `False` whenever `state_store.get_state(self.scope, tmcc_id, False)` yields nothing, so an unknown ID can never leave entry mode.\n\n**The creation primitive already exists**, in the `Set` branch immediately above (`keypad_view.py:577`):\n\n```python\nstate = ComponentStateStore.get_state(host.scope, tmcc_id, create=False)\nif state is None:\n    state = ComponentStateStore.get_state(host.scope, tmcc_id, create=True)\n    state.initialize(scope=host.scope, tmcc_id=tmcc_id)\n    host.ops_mode(update_info=True, state=state)\n    host.on_info(state=state)\n```\n\n`ComponentStateStore.get_state(create=True)` indexes the `ComponentStateDict` default-dict, so the state becomes a real store entry. `CompDataMixin.initialize` (`db/comp_data.py:246`) builds an `AccessoryData` / `SwitchData` with `_empty = True` and `_comp_data_record = True`, so `is_comp_data_empty` stays `True` until the Base 3 answers — which is exactly the marker that distinguishes \"provisional\" from \"real\".\n\n**Panel selection** is centralized in `KeypadView._panel_kind_for` (`keypad_view.py:130`), read both by `apply_ops_mode_ui_non_engine` for the keys it draws and by `EngineGui._accessory_contexts` for the gamepad chain via `PANEL_CONTEXT_CHAINS`.\n\n**Naming** already works: `StateInfoOverlay._on_road_name_edited` / `_on_road_number_edited` build `comp_data.set_road_name_req` / `set_road_number_req` and dispatch through `BaseReq.process_sync_reqs`.\n\n**Reachability of the info panel today**: `EngineGui._bind_image_long_press` puts `on_info` on the image's `SwipeDetector`. But `_refresh_component_view` hides `image_box` for any scope outside `{ENGINE, TRAIN, ACC}` — so a **Switch has no long-press route to the info panel at all**. The new `Info` key closes that hole.\n\n### Key Decisions\n\n| Decision | Choice | Rationale |\n| --- | --- | --- |\n| Creation mechanism | Reuse the `Set` key's `get_state(create=True)` + `comp_data.initialize` pair | Already proven in production code; no new persistence path |\n| Panel override storage | Single transient `_forced_panel_kind` on `KeypadView` (your choice) | Keeps `_panel_kind_for` the one decision point, so screen and gamepad cannot disagree |\n| Recents/catalog entry | Deferred until named (your choice) | Mistyped IDs leave nothing behind |\n| Provisional marker | `state.is_comp_data_empty` plus an explicit `EngineGui._provisional` set | The flag alone is ambiguous — a real but not-yet-fetched state is also \"empty\"; the set records *we* created it |\n| Generic-panel exit key | Extend the existing `ac_op_btn` rather than add a cell | It already means \"go to the more specific view of this ID\" and already sits in the one free generic-panel slot |\n| New key placement | Column 3 (the 4th column), row 2 | Verified empty: `Set`=[3,0], toggle-direction=[3,1], `Aux1`=[3,3], `Aux2`=[3,4]; column 4 is the throttle slider |\n\n### Proposed Changes\n\n**1. `keypad_view.py` — the `↵` branch**\n\n```python\nelif key == ENTER_KEY:\n    self._reset_on_keystroke = False\n    entered = int(tmcc_id)\n    if host.make_recent(host.scope, entered):\n        host.ops_mode()\n    elif self._can_create(host.scope, entered):\n        state = host.create_provisional_component(host.scope, entered)\n        host.ops_mode(update_info=True, state=state)\n    else:\n        self.entry_mode(clear_info=False)\n```\n\n`_can_create` gates on `scope in CREATABLE_SCOPES` (`{ACC, SWITCH}`) and the `Set` key's existing range rule. `CREATABLE_SCOPES` is derived from `SCOPE_TO_SET_ENUM` minus `ENGINE`, so adding Engines later is a one-line change.\n\n**2. `engine_gui.py` — provisional bookkeeping**\n\n```python\nself._provisional: set[tuple[CommandScope, int]] = set()\n\ndef create_provisional_component(self, scope: CommandScope, tmcc_id: int) -> ComponentState:\n    state = self._state_store.get_state(scope, tmcc_id, False)\n    if state is None:\n        state = ComponentStateStore.get_state(scope, tmcc_id, create=True)\n        state.initialize(scope=scope, tmcc_id=tmcc_id)\n    self._provisional.add((scope, tmcc_id))\n    self._scope_tmcc_ids[scope] = tmcc_id\n    return state\n\ndef is_provisional(self, scope, tmcc_id) -> bool: ...\ndef promote_component(self, state) -> None:      # clears the flag, make_recent,\n    ...                                          # _request_options_rebuild,\n                                                 # _reset_catalog_configured_accessories\n```\n\n- `_update_recent_selection` skips `make_recent` while the selection is provisional (FR-3).\n- `on_new_switch` / `on_new_accessory` call `promote_component` when a provisional state stops reporting `is_comp_data_empty` — i.e. the Base 3 answered.\n- `_rebuild_state_caches` discards the provisional entry when a state is deleted.\n\n**3. `state_info_overlay.py` — promotion hook**\n\n`_on_road_name_edited` and `_on_road_number_edited` gain a single trailing call to `self.gui.promote_component(state)` after the request is dispatched. Nothing else in the overlay changes; the existing `reset_visibility(scope, ...)` already renders the right field set for `ACC`, and `SwitchState` (a `TmccState, LcsProxyState`) is handled by the default/None-scope fields.\n\n**4. `keypad_view.py` — the override and the new keys**\n\n```python\n@property\ndef panel_kind_override(self) -> str | None: ...\ndef set_panel_kind_override(self, kind: str | None) -> None: ...\n\ndef _panel_kind_for(self, state):\n    if not self.is_accessory_or_bpc2 or state is None:\n        return None\n    if self._forced_panel_kind is not None:\n        return self._forced_panel_kind\n    ...   # unchanged flag rules\n```\n\nCleared from `entry_mode`, from `EngineGui.on_scope`, and from `update_component_info` when `selection_changed` — FR-5.\n\nNew cells built in `KeypadView.build` next to the existing aux/BPC2 cells:\n\n- `host.info_cell` / `host.info_btn` — grid `[3, 2]`, `command=host.on_info`, shown by the `PANEL_GENERIC` branch and the `SWITCH` branch of `apply_ops_mode_ui_non_engine`.\n- `host.sw_set_cell` / `host.sw_set_btn` — grid `[3, 0]`, `on_press=(host.on_set_key, [CommandScope.SWITCH, ...])`, shown by the `SWITCH` branch. `on_set_key` already resolves `TMCC1SwitchCommandEnum.SET_ADDRESS` out of `SCOPE_TO_SET_ENUM`.\n- `host.acc_generic_cell` / `host.acc_generic_btn` — grid `[3, 2]` on the BPC2/ASC2 panels (column 3 is entirely free there), `command=host.on_show_generic_acc_panel`.\n\n**5. Exit from the generic panel**\n\n`enable_acc_view` is generalized into `enable_alternate_acc_view`: `ac_op_btn` at `[1, 4]` keeps today's meaning (open the configured-accessory overlay) whenever no override is in force, and becomes \"return to the native LCS panel\" when `_forced_panel_kind` is set and the state has a native kind. One key, one meaning — *the other view of this ID*.\n\n**6. The two keypad-less panels**\n\n- **Sensor Track**: `host.sensor_track_box` is a `TitleBox` holding only the `CheckBoxGroup`; a compact full-width `HoldButton` is appended below the group.\n- **AMC2**: `Amc2OpsPanel._header` (a `Box` at grid `[0, 0]`) gains one small button; `Amc2OpsPanel` exposes it so `KeypadView` can wire the command without reaching into privates.\n\n**7. `engine_gui.py` — the toggle handlers**\n\n```python\ndef on_show_generic_acc_panel(self) -> None:\n    self._keypad_view.set_panel_kind_override(PANEL_GENERIC)\n    self.ops_mode(update_info=False)\n\ndef on_show_native_acc_panel(self) -> None:\n    self._keypad_view.set_panel_kind_override(None)\n    self.ops_mode(update_info=False)\n```\n\nBoth close any open popup first via `self._popup.close()`, matching every other panel transition.\n\n### Data Models / Contracts\n\n```python\n# engine_gui_conf.py\nINFO_KEY = \"Info\"\nACC_PANEL_KEY = \"Acc\"      # LCS panel -> generic\nLCS_PANEL_KEY = \"LCS\"      # generic  -> LCS panel\nCREATABLE_SCOPES: frozenset[CommandScope] = frozenset({CommandScope.ACC, CommandScope.SWITCH})\n\n# EngineGui\ndef create_provisional_component(self, scope: CommandScope, tmcc_id: int) -> ComponentState\ndef is_provisional(self, scope: CommandScope, tmcc_id: int) -> bool\ndef promote_component(self, state: ComponentState | None = None) -> bool\ndef on_show_generic_acc_panel(self) -> None\ndef on_show_native_acc_panel(self) -> None\n\n# KeypadView\npanel_kind_override: str | None                       # read-only property\ndef set_panel_kind_override(self, kind: str | None) -> None\ndef _can_create(self, scope: CommandScope, tmcc_id: int) -> bool\n```\n\n### Components\n\n| Component | Change |\n| --- | --- |\n| `KeypadView.on_keypress` | `↵` gains the create path for `ACC` / `SWITCH` |\n| `KeypadView._panel_kind_for` | Consults the new transient override first |\n| `KeypadView.build` | Three new keypad cells; Sensor Track box gains a footer button |\n| `KeypadView.apply_ops_mode_ui_non_engine` | Shows `Info` on generic + switch, `Set` on switch, the generic-panel toggle on BPC2/ASC2 |\n| `KeypadView.enable_acc_view` | Generalized to serve both \"configured overlay\" and \"back to LCS\" |\n| `EngineGui` | Provisional set, create/promote API, two toggle handlers, override clearing |\n| `StateInfoOverlay` | Promotion call after a Road Name / Road Number commit |\n| `Amc2OpsPanel` | One header button, exposed for wiring |\n| `SteamDeckGui` | **No change** — it hosts `EngineGui` panes, so it inherits all of it |\n| `accessory_bindings.py` | **No change** — chains are keyed by reported panel kind |\n\n### File Structure\n\n```\nsrc/pytrain/gui/controller/\n  engine_gui.py            (modified)  provisional API, toggle handlers, override clearing\n  keypad_view.py           (modified)  create-on-Enter, override, new cells, ops-mode wiring\n  engine_gui_conf.py       (modified)  INFO_KEY, ACC_PANEL_KEY, LCS_PANEL_KEY, CREATABLE_SCOPES\n  state_info_overlay.py    (modified)  promote on name/number commit\n  amc2_ops_panel.py        (modified)  header panel-toggle button\n\ntests/gui/\n  test_gui_checkpoint.py           (new)       behavior-locking baseline\n  test_engine_gui_create.py        (new)       creation + promotion\n  test_keypad_view.py              (modified)  new cells, override, Enter path\n  test_engine_gui_accessories.py   (modified)  panel toggling\n  test_engine_gui_transitions.py   (modified)  override lifetime\n  test_state_info_overlay.py       (modified)  promotion hook\n```\n\n### Architecture Diagram\n\n```mermaid\ngraph TD\n    K[\"KeypadView.on_keypress<br/>Enter key\"] -->|existing state| MR[\"EngineGui.make_recent\"]\n    K -->|unknown id, ACC or SWITCH| CP[\"EngineGui.create_provisional_component\"]\n    CP --> CS[\"ComponentStateStore.get_state create=True<br/>+ comp_data.initialize\"]\n    CP --> PS[\"_provisional set\"]\n    MR --> OM[\"EngineGui.ops_mode\"]\n    CP --> OM\n    OM --> AP[\"KeypadView.apply_ops_mode_ui_non_engine\"]\n    AP --> PK[\"_panel_kind_for\"]\n    OV[\"_forced_panel_kind<br/>transient override\"] --> PK\n    PK --> DRAW[\"Keys drawn:<br/>generic / bpc2 / asc2 / sensor_track / amc2\"]\n    PK --> CTX[\"EngineGui.input_contexts<br/>PANEL_CONTEXT_CHAINS\"]\n    CTX --> PAD[\"Steam Deck input layer\"]\n    DRAW --> INFO[\"Info key\"]\n    DRAW --> TOG[\"Panel toggle keys\"]\n    TOG --> OV\n    INFO --> SIO[\"StateInfoOverlay\"]\n    SIO -->|road name / number committed| PROM[\"EngineGui.promote_component\"]\n    PROM --> PS\n    PROM --> REC[\"recents + header Combo + CatalogPanel\"]\n```\n\n### Risks\n\n| Risk | Mitigation |\n| --- | --- |\n| A provisional state lingers in the store after you navigate away | It is a normal store entry with empty comp data, indistinguishable from an unfetched one, and stays out of recents/catalog; `_rebuild_state_caches` already drops deleted states |\n| Grid collision for the new keys | Column 3 row 2 verified empty on the generic panel; column 3 verified entirely free on BPC2/ASC2; entry/ops cells already share slots by design |\n| Compact (Deck) pane overflow | No rows or columns added; the Sensor Track footer button is the one height change and that box is already the tallest case, guarded by `sensor_track_row_pady` |\n| Screen and gamepad disagreeing after a toggle | The override lives *inside* `_panel_kind_for`, the single property both read |\n| `on_info` treating a provisional record as pre-existing | `on_info` already computes `is_new = state.is_comp_data_empty`, which is `True` for a freshly initialized record |\n| Frozen-surface compatibility tests | `tests/gui/controller/test_engine_gui_compatibility.py` asserts the constructor's `GuiZeroBase` kwargs, which are untouched; new methods are additive |"},{"name":"Testing","content":"### Validation Approach\n\nThe suite is fully headless — `tests/gui/test_keypad_view.py` and friends drive `KeypadView` and `EngineGui` against hand-rolled `DummyTk` / `DummyWidget` / `SimpleNamespace` fakes, with no display and no Base 3. Everything below is therefore checkable by the agent.\n\nThe checkpoint you asked for is **stage one**: a new `tests/gui/test_gui_checkpoint.py` that asserts today's behavior and is committed *before* any production change, so every later stage runs against a red/green signal rather than a hunch.\n\n### Key Scenarios\n\n**Checkpoint (locks current behavior)**\n\n- For each scope, `apply_ops_mode_ui_non_engine` shows exactly the cells it shows today (route → fire only; switch → thru + out; generic acc → aux cells expanded, accessory keys active, throttle box; bpc2 → on/status/off; asc2 → adds Aux1; sensor track → sequence box, keypad hidden; amc2 → amc2 box, keypad hidden).\n- `_panel_kind_for` returns the documented kind for every state-flag combination, including ASC2 winning over BPC2.\n- `PANEL_CONTEXT_CHAINS` lookups for every kind, and `input_contexts` for switch / route / accessory-with-nothing-selected.\n- `↵` on an unknown ID currently returns to entry mode in **all** scopes.\n- `entry_mode` / `enter_ops_mode_base` cell visibility and aux collapse/expand grids.\n\n**Creation**\n\n- `↵` + unknown ACC ID → state created, `comp_data` initialized, ops mode entered, generic panel drawn.\n- `↵` + unknown SWITCH ID → state created, switch panel drawn with the new `Set` and `Info` keys visible.\n- `↵` + unknown ENGINE / TRAIN / ROUTE ID → still returns to entry mode.\n- `↵` + out-of-range ID (`0`, `1`, `99`, `>98`) in ACC scope → still returns to entry mode.\n- The existing `Set`-key create path keeps working unchanged.\n\n**Deferred promotion**\n\n- After creation, the ID is absent from `get_options()` and from the recents deque.\n- `StateInfoOverlay._on_road_name_edited` on a provisional state → `promote_component` runs, `make_recent` is called, options are rebuilt, catalog cache reset.\n- Same for `_on_road_number_edited`.\n- A Base-3 record arriving for a provisional ID promotes it without an edit.\n- Selecting a provisional ID, leaving, and returning leaves recents unchanged.\n\n**Panel toggling**\n\n- BPC2 / ASC2 ops mode shows the generic-panel toggle; pressing it sets the override, re-enters ops mode, and draws the generic panel.\n- With the override in force, `accessory_panel_kind` reports `generic` and `input_contexts` yields the `acc_generic` chain — the screen/pad-agreement invariant.\n- The generic panel's `ac_op_btn` returns to the native panel when the override is set, and still opens the configured-accessory overlay when it is not.\n- Sensor Track and AMC2 toggles reach the generic panel and back.\n- Override clears on change of TMCC ID, change of scope, and on `entry_mode`.\n\n**Info key**\n\n- `Info` on the generic accessory panel calls `on_info` for the current scope + ID.\n- `Info` on the switch panel does the same — the only route to the info panel there, since `image_box` is hidden for switch scope.\n- `Info` is hidden in entry mode and on engine/train ops screens.\n\n### Edge Cases\n\n- An ID that is LCS-backed but matches none of the four named kinds still reports `generic` (existing rule, re-asserted).\n- `Clear` stays disabled in the info overlay for LCS-backed states (`is_deletable` is `False`).\n- A provisional state that is deleted while selected — `_rebuild_state_caches` drops the provisional entry and does not re-add it to recents.\n- Toggling to generic on an ID that has *both* a configured accessory and an LCS panel — the exit key resolves to one destination deterministically.\n- Compact (`_compact=True`) construction of every new cell, so no Deck-only geometry path is left untested.\n- The Sensor Track footer button does not disturb the ten-row cursor stepping (`step_sensor_track_sequence` clamping still asserted).\n\n### Test Changes\n\n- **New** `tests/gui/test_gui_checkpoint.py` — the baseline, committed first.\n- **New** `tests/gui/test_engine_gui_create.py` — creation, provisional bookkeeping, promotion.\n- **Modified** `tests/gui/test_keypad_view.py` — `↵` create path, override, new cells.\n- **Modified** `tests/gui/test_engine_gui_accessories.py` — panel toggling across all four LCS kinds.\n- **Modified** `tests/gui/test_engine_gui_transitions.py` — override lifetime across scope/selection changes.\n- **Modified** `tests/gui/test_state_info_overlay.py` — promotion hook.\n- **Verified unchanged** `tests/gui/controller/test_accessory_bindings.py`, `test_steam_deck_input.py`, `test_engine_gui_compatibility.py`.\n\nEach stage ends with `../bin/python -m ruff format --check <changed files>` and the full `../bin/python -m pytest`, per the project instructions."},{"name":"Open Questions","content":"### Answered\n\n- **Focus** — Accessories and Switches only this pass; Engines in a later turn.\n- **Create trigger** — `↵` on an undefined ID goes straight to the generic operating screen, augmented with `Set` and `Info` where missing; no confirmation dialog, no auto-popup.\n- **Info key** — generic Accessory panel and Switch panel.\n- **Panel toggle** — BPC2, ASC2, Sensor Track and AMC2 all get it.\n- **Override storage** — single transient flag on `KeypadView`.\n- **Recents/catalog** — provisional records appear only after naming.\n- **Checkpoint** — behavior-locking headless test module.\n\n### Nothing blocking\n\nI have what I need to start. Three cosmetic points I will decide by matching existing style unless you say otherwise — all cheap to change later:\n\n1. **Key labels.** I plan text labels — `Info`, and `Acc` / `LCS` for the two toggle directions — rather than new artwork, since `Set`, `Aux1` and `Aux2` in the same column are already text. If you would rather have images, `op-acc.jpg` is already preloaded and I can point the toggle at it.\n2. **Toggle placement on Sensor Track.** That panel replaces the whole keypad, so its toggle goes below the Sequence list as a full-width button. On AMC2 it goes in the existing header row beside the output selector.\n3. **Gamepad access.** I am not binding the new keys to controller buttons, since you did not ask and the face buttons are heavily committed already. Say the word and I will add them to the `acc_generic` / `acc_bpc2` / `acc_asc2` context tables.\n\n### One thing worth flagging\n\nThe Switch operating screen currently hides `image_box` (`_refresh_component_view` only shows it for `ENGINE`, `TRAIN` and `ACC`), so there is **no long-press target there at all** — switches have never had a route to the info panel. The new `Info` key is therefore not just a convenience on that screen; it is the only way in. Worth knowing in case you had assumed long-press worked for switches and it merely seemed unresponsive."}],
 - "delivery_plan"=[{"name":"Checkpoint current GUI behavior with a baseline test module","description":"A new headless test module locks today's panel selection, cell visibility and transitions for every scope, committed before any production code changes, so later stages have a real regression signal.\n\n- Add `tests/gui/test_gui_checkpoint.py` in the style of `tests/gui/test_engine_gui_transitions.py`, reusing its `DummyTk` / `DummyWidget` fakes.\n- Assert `KeypadView._panel_kind_for` for every accessory state-flag combination, including ASC2 taking precedence over BPC2 and an unrecognized LCS port falling through to `generic`.\n- Assert the exact cells `apply_ops_mode_ui_non_engine` shows for each scope: route (fire only), switch (thru + out), generic accessory (aux cells expanded, accessory keys active, throttle box shown), BPC2 (on/status/off), ASC2 (adds Aux1), Sensor Track (sequence box, keypad hidden), AMC2 (amc2 box, keypad hidden).\n- Assert `EngineGui.input_contexts` and `_accessory_contexts` resolve through `PANEL_CONTEXT_CHAINS` for every panel kind, plus the switch, route and nothing-selected cases.\n- Assert today's dead end explicitly: `↵` on an unknown TMCC ID returns to entry mode in all five scopes.\n- Assert `entry_mode` / `enter_ops_mode_base` cell visibility and the aux `render_grid` / `reset_grid` collapse-expand behavior.\n- Run `ruff format --check` on the new file and the full `pytest` suite to confirm the baseline is green."},{"name":"Create Accessory and Switch records from the Enter key","description":"Pressing `↵` on an undefined Accessory or Switch ID materializes a provisional record and enters ops mode instead of bouncing back to the entry keypad.\n\n- Add `CREATABLE_SCOPES = frozenset({CommandScope.ACC, CommandScope.SWITCH})` to `engine_gui_conf.py`, derived alongside `SCOPE_TO_SET_ENUM` so Engines can be added later in one line.\n- Add `EngineGui.create_provisional_component(scope, tmcc_id)`: resolve via `state_store.get_state(..., False)`, and when absent call `ComponentStateStore.get_state(..., create=True)` plus `state.initialize(scope=..., tmcc_id=...)` — the same pair the `Set` key already uses.\n- Add `EngineGui._provisional: set[tuple[CommandScope, int]]` and `is_provisional(scope, tmcc_id)`.\n- Rework the `ENTER_KEY` branch of `KeypadView.on_keypress`: keep the `make_recent` fast path, add a `_can_create` path (scope in `CREATABLE_SCOPES`, `2 <= id <= 98`, `id != 99`) that creates and enters ops mode, and leave the `entry_mode` fallback for everything else.\n- Make `EngineGui._update_recent_selection` skip `make_recent` while the selection is provisional, so nothing reaches recents or the header `Combo` yet.\n- Drop provisional entries in `_rebuild_state_caches` when a state is deleted.\n- Add `tests/gui/test_engine_gui_create.py` covering creation for ACC and SWITCH, unchanged behavior for ENGINE/TRAIN/ROUTE, rejection of out-of-range IDs (`0`, `1`, `99`, `>98`), and absence from recents.\n- Run `ruff format --check` on the changed files and the full `pytest` suite."},{"name":"Add Info and Set keys to the generic Accessory and Switch screens","description":"Both screens carry an `Info` key in the 4th column that opens the StateInfoPanel, the Switch screen gains its own `Set` key, and committing a Road Name or Road Number promotes a provisional record into recents and the catalog.\n\n- Add `INFO_KEY` to `engine_gui_conf.py`.\n- In `KeypadView.build`, create `host.info_cell` / `host.info_btn` at grid `[3, 2]` — the verified-empty slot in column 3, between the aux `Set` at `[3, 0]`/toggle at `[3, 1]` and `Aux1`/`Aux2` at `[3, 3]`/`[3, 4]` — wired to `host.on_info`.\n- Create `host.sw_set_cell` / `host.sw_set_btn` at grid `[3, 0]` wired to `host.on_set_key` with `CommandScope.SWITCH`, which already resolves `TMCC1SwitchCommandEnum.SET_ADDRESS` through `SCOPE_TO_SET_ENUM`.\n- Show `info_cell` from the `PANEL_GENERIC` branch and the `SWITCH` branch of `apply_ops_mode_ui_non_engine`; show `sw_set_cell` from the `SWITCH` branch only; keep both out of `entry_cells` so `entry_mode` hides them.\n- Add `EngineGui.promote_component(state)`: clear the provisional entry, call `make_recent`, `_request_options_rebuild()` and `_reset_catalog_configured_accessories()`.\n- Call `promote_component` from `StateInfoOverlay._on_road_name_edited` and `_on_road_number_edited` after the request is dispatched.\n- Promote automatically from `on_new_accessory` / `on_new_switch` when a provisional state stops reporting `is_comp_data_empty`, i.e. the Base 3 answered.\n- Extend `tests/gui/test_engine_gui_create.py`, `test_keypad_view.py` and `test_state_info_overlay.py` for key visibility per scope, `on_info` dispatch, and both promotion routes.\n- Run `ruff format --check` on the changed files and the full `pytest` suite."},{"name":"Toggle between LCS-specific and generic Accessory panels","description":"BPC2, ASC2, Sensor Track and AMC2 screens each get a key that switches to the generic Accessory panel, and the generic panel gets a key back — with the Steam Deck gamepad context following the screen automatically.\n\n- Add `ACC_PANEL_KEY` and `LCS_PANEL_KEY` labels to `engine_gui_conf.py`.\n- Add `KeypadView._forced_panel_kind`, a read-only `panel_kind_override` property and `set_panel_kind_override(kind)`; have `_panel_kind_for` consult it before the state-flag rules, so screen and gamepad keep sharing one decision point.\n- Clear the override from `entry_mode`, from `EngineGui.on_scope`, and from `update_component_info` when `selection_changed` — the transient lifetime you chose.\n- Add `host.acc_generic_cell` / `acc_generic_btn` at grid `[3, 2]` on the BPC2/ASC2 panels, where column 3 is entirely free, wired to `EngineGui.on_show_generic_acc_panel`.\n- Add a full-width `HoldButton` below the `CheckBoxGroup` inside `host.sensor_track_box`, and a small button in `Amc2OpsPanel._header` exposed for `KeypadView` to wire, since both panels replace the keypad entirely.\n- Generalize `KeypadView.enable_acc_view` into `enable_alternate_acc_view`: `ac_op_btn` at `[1, 4]` keeps opening the configured-accessory overlay when no override is in force, and returns to the native LCS panel when one is.\n- Add `EngineGui.on_show_generic_acc_panel` and `on_show_native_acc_panel`, each closing any open popup then re-entering `ops_mode(update_info=False)`.\n- Extend `tests/gui/test_engine_gui_accessories.py` and `test_engine_gui_transitions.py`: toggling from all four LCS kinds, the return path, `accessory_panel_kind` reporting `generic` under the override, `input_contexts` yielding the `acc_generic` chain, and override clearing on ID/scope/entry-mode changes.\n- Run `ruff format --check` on the changed files and the full `pytest` suite."},{"name":"Verify compact Steam Deck parity and finish the regression pass","description":"The new keys render correctly on both Steam Deck panes as well as portrait, and the whole suite including the stage-one checkpoint is green.\n\n- Exercise every new cell through a `_compact=True` construction path in the tests, covering `fit_image_box_size`, `info_box_height` and `sensor_track_row_pady`, so no Deck-only geometry branch is left unasserted.\n- Confirm `SteamDeckGui` needs no change by asserting that a pane-hosted `EngineGui` (with `parent` and `parent_gui` set) exposes the same creation, Info and toggle behavior as a standalone one.\n- Re-assert the Sensor Track cursor contract after the footer button is added: `step_sensor_track_sequence` clamping at both ends, and the dot-versus-cursor separation the panel depends on.\n- Reconcile the stage-one checkpoint module with intended changes: update only the assertions that encode the old dead-end behavior, leaving every other locked assertion untouched as proof of no collateral regression.\n- Confirm `tests/gui/controller/test_accessory_bindings.py`, `test_steam_deck_input.py` and `test_engine_gui_compatibility.py` still pass unmodified.\n- Run `../bin/python -m ruff format --check` on all changed Python files, fix with `ruff format` if needed, then run the full `../bin/python -m pytest`."}]
</previous_issue_solution>
<previous_issue>
## Orchestrated Plan Task
implement according to the plan
</previous_issue>
<previous_issue_solution>
### Summary
- Implemented the planned Accessory/Switch GUI enhancements: undefined ACC/SWITCH IDs can now be created from Enter, named via Info, and toggled between generic and LCS-specific accessory panels.
- Completed the regression/parity pass with headless checkpoint and compact/Steam Deck coverage; full suite is green.

### Changes
- Added a baseline checkpoint test module, then updated it only where intended as behavior changed.
- Implemented provisional component creation/bookkeeping plus deferred promotion into recents/catalog after naming or real Base-3 data arrival.
- Added `Info` on generic accessory and switch screens, `Set` on switch, and transient panel override/toggle flow for BPC2, ASC2, Sensor Track, and AMC2.
- Added compact/pane-hosted parity tests confirming `EngineGui` changes carry through Steam Deck hosting without `SteamDeckGui` code changes.

### Verification
- `../bin/python -m ruff format --check` passed on all changed Python files.
- `../bin/python -m pytest -q` passed: 2046 tests green.

### Notes
- No git/PR workflow was activated because the user asked for implementation only, not branch or PR packaging.
</previous_issue_solution>
<previous_issue>
## Plan Task
This is great! Is there a way to not show the 4th column unless it contains active buttons? I don't like seeing the empty column on the Entry views
</previous_issue>
<previous_issue>
## Plan Task
This is great! Is there a way to not show the 4th column unless it contains active buttons? I don't like seeing the empty column on the Entry views
</previous_issue>
<previous_issue_solution>
tool name: submit
tool parameters:
</previous_issue_solution>
<previous_issue>
## Orchestrated Plan Task
This is great! Is there a way to not show the 4th column unless it contains active buttons? I don't like seeing the empty column on the Entry views
</previous_issue>
<previous_issue_solution>
### Summary
- Implemented dynamic keypad-column reflow in `KeypadView` so the 4th column collapses when it has no visible buttons and re-expands automatically when needed.
- Entry and empty-column ops views now render as a tight 3-wide keypad, with Portrait and pane-hosted/compact Steam Deck behavior kept in parity.

### Changes
- Added tracked keypad-cell registration plus `_reflow_keypad_columns()` to collapse/restore columns from live cell visibility and current grid placement, including relocated aux cells and the throttle column.
- Wired reflow into `entry_mode` and all keypad-based ops transitions so route/entry collapse while switch, generic accessory, and BPC2/ASC2 expand correctly.
- Extended `test_keypad_view.py`, `test_gui_checkpoint.py`, and `test_gui_deck_parity.py` to lock occupancy, width tightening, transition behavior, and compact/pane-hosted parity.

### Verification
- `../bin/python -m ruff format --check src/pytrain/gui/controller/keypad_view.py tests/gui/test_keypad_view.py tests/gui/test_gui_checkpoint.py tests/gui/test_gui_deck_parity.py`
- `../bin/python -m pytest -q` → 2082 passed

</previous_issue_solution>
<previous_issue>
## Plan Task
Modify the default BPC screen such that the "Acc" button is repositioned below the "9" key and above the "Off" key. Also, add 3 dots (elipsese) after so it becomes "Acc...". Pressing "Acc" correctly displayed the generic Acc panel, but the button directly below the "0" key sometimes displayed as an operating accessory, sometimes displayed as the text "LCS" in a very tiny font. Generate B&W icons in the style of op_milk_loader.jpg, op_station.jpg, etc., depicting a BPC2 and an operating screen. Confirm your understanding of this request before implementing.

When selecting the TMCC of an Asc2-backed operating accessory, the initial display is of the Operating Accessorie's control panel, which is correct. Pressing the "LCS ASC2" button correctly displays the native Acc panel, as I had requested. Add elipses to the "Acc" button, as above, and add a "Set" button that sends the ACC SET_ADDRESS command, as well as a new "LCS..." button. For now, this button will be a NOOP. It's behavior will be specified in a later turn.
</previous_issue>
<assistant_question>
<UPDATE>
<PREVIOUS_STEP>Confirmed icons live in `src/pytrain/gui/images/` as flat black-silhouette artwork (e.g. `op-station.jpg` with a control-panel inset), and Pillow is already a dependency. The panel-toggle button is `ac_op_btn`; its "LCS" label comes from `enable_native_acc_view` (`LCS_PANEL_KEY`), while `accessory_type` yields "LCS ASC2" for display elsewhere. The genuine ambiguities are how to produce the new B&W icons, what each depicts, and where the new ASC2 Set/LCS keys sit.</PREVIOUS_STEP>
<EXTERNAL>I've traced the whole flow: the accessory icons are flat black artwork in `src/pytrain/gui/images/`, Pillow is available for generating new ones, and the shape-shifting button below the numbers is `ac_op_btn`, whose tiny "LCS" text comes from `enable_native_acc_view` in `keypad_view.py`. Before writing the plan I need to confirm a few choices with you — chiefly how the new BPC2/operating-screen icons should be produced and what they depict, plus where the new Set and "LCS..." keys belong on the ASC2 panel — since those decisions shape the implementation.</EXTERNAL>
</UPDATE>
tool name: ask_user
tool parameters:
 - "questions"=[{"name":"Icon Production","question":"The existing op-*.jpg icons (e.g. op-station.jpg, op-milk-loader.jpg) are detailed hand/AI-drawn black silhouettes on white. How should I produce the new B&W BPC2 / operating-screen icons for the toggle button? (Understanding: these replace the tiny 'LCS' text and the op-acc image on the ac_op_btn.)","options":[{"title":"You supply artwork","description":"You drop final .jpg files into src/pytrain/gui/images and I only wire them into the buttons — guarantees the polished silhouette style matches the existing set exactly."},{"title":"I draw with Pillow now","description":"I generate clean flat B&W icons programmatically (Pillow is already a dependency): a BPC2 terminal-block box and a control-screen with sliders/buttons — simpler than the hand-drawn art but consistent and immediately usable."},{"title":"Pillow placeholders","description":"I generate simple placeholder icons now under the intended filenames so behavior is complete, and you can later overwrite them with polished artwork without any code change."}],"allowMultiple":false},{"name":"Icon Set","question":"What should the icon(s) depict, given the button toggles between the operating-accessory view and the LCS device view, and the panel can be BPC2 or ASC2?","options":[{"title":"Two icons: device + screen","description":"One depicting an LCS device (used to return to the native BPC2/ASC2 panel) and one depicting an operating screen (used to go to the operating-accessory view), so each toggle direction has its own clear icon."},{"title":"Per-device: BPC2, ASC2, screen","description":"Three icons — a BPC2, an ASC2, and a generic operating screen — so each LCS panel shows its own device rather than a shared one."},{"title":"One BPC2 composite","description":"A single BPC2+operating-screen composite icon for the return-to-LCS direction only; keep the existing op-acc.jpg for the operating-accessory direction."}],"allowMultiple":false},{"name":"ASC2 New Keys","question":"On the ASC2 native panel, where should the new 'Set' (sends ACC SET_ADDRESS) and 'LCS...' (NOOP for now) keys go, alongside the 'Acc...' key that moves below '9' and above 'Off' (into the Enter-key slot at column 2, row 3, which is free in ops mode)? Should 'Set' also be added to the BPC2 panel?","options":[{"title":"Column 3 stack, ASC2 only","description":"Place 'Set' and 'LCS...' in the free 4th column (column 3) rows 0-1 on ASC2 only; BPC2 stays as-is (it reaches Set Address via the generic panel), keeping the LCS cluster on the right edge."},{"title":"Column 3 stack, Set on both","description":"Same column-3 placement, but also add a 'Set' key to the BPC2 panel so SET_ADDRESS is reachable directly on both LCS panels."},{"title":"Bottom action band","description":"Group 'Acc...', 'Set', and 'LCS...' together as a row near the On/Status/Off action band rather than in the right column."}],"allowMultiple":false}]
</assistant_question>
<user_answer>
### Response for the question "Icon Production"
Selected options: I draw with Pillow now

### Response for the question "Icon Set"
Selected options: Per-device: BPC2, ASC2, screen

### Response for the question "ASC2 New Keys"
Selected options: Column 3 stack, ASC2 only
</user_answer>
<previous_issue_solution>
tool name: submit
tool parameters:
</previous_issue_solution>
</plan_session_history>

<plan_task>
Modify the default BPC screen such that the "Acc" button is repositioned below the "9" key and above the "Off" key. Also, add 3 dots (elipsese) after so it becomes "Acc...". Pressing "Acc" correctly displayed the generic Acc panel, but the button directly below the "0" key sometimes displayed as an operating accessory, sometimes displayed as the text "LCS" in a very tiny font. Generate B&W icons in the style of op_milk_loader.jpg, op_station.jpg, etc., depicting a BPC2 and an operating screen. Confirm your understanding of this request before implementing.

When selecting the TMCC of an Asc2-backed operating accessory, the initial display is of the Operating Accessorie's control panel, which is correct. Pressing the "LCS ASC2" button correctly displays the native Acc panel, as I had requested. Add elipses to the "Acc" button, as above, and add a "Set" button that sends the ACC SET_ADDRESS command, as well as a new "LCS..." button. For now, this button will be a NOOP. It's behavior will be specified in a later turn.
</plan_task>

This task has no prior planning phase. Before implementation, analyze the task and codebase, define acceptance criteria if not explicitly provided in the task description, and plan your approach. 
The Reviewer must independently define its own acceptance criteria and will verify them.

### ✓ Step 2: Update / Follow-up
We are very close. On an Operating accessory, the transition from Operating screen to the LCS device control screen is as I want. That screen now shows the operating-accessory-specific image to return to the Operating control screen, and pressing "Acc..." correctly goes to the generic accessory screen. That screen shows your new "op-asc2.jpg" icon, which, upon press, returns to the Operating screen. This is incorrect. That icon should be the same operating-accessory-specific image shown on the LCS device screen.
