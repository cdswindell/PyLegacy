# SPDX-License-Identifier: LGPL-3.0-only
"""Regression coverage for real multiprocessing worker imports."""

import multiprocessing
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest


@pytest.mark.parametrize("method", ["fork", "spawn", "forkserver"])
def test_worker_import_does_not_rotate_main_log(tmp_path: Path, method: str):
    if method not in multiprocessing.get_all_start_methods():
        pytest.skip(f"{method} unavailable on this platform")

    script = tmp_path / "worker_logging.py"
    script.write_text(
        textwrap.dedent(
            """
            import logging
            import multiprocessing
            import os
            from pathlib import Path

            def worker():
                import src.pytrain.cli.pytrain
                logging.getLogger("worker").warning("worker message")

            if __name__ == "__main__":
                from src.pytrain.utils.logging_manager import LoggingManager

                assert LoggingManager.initialize(logfile_file="pytrain.log")
                logging.info("before worker")
                ctx = multiprocessing.get_context(os.environ["PYTRAIN_TEST_METHOD"])
                process = ctx.Process(target=worker)
                process.start()
                process.join(timeout=30)
                assert process.exitcode == 0, process.exitcode
                logging.info("after worker")
                assert not Path("pytrain.log.1").exists(), "worker rotated logfile"
                content = Path("pytrain.log").read_text(encoding="utf-8")
                assert "before worker" in content
                assert "after worker" in content
            """
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    root = Path(__file__).resolve().parents[2]
    env["PYTHONPATH"] = os.pathsep.join(filter(None, (str(root), env.get("PYTHONPATH", ""))))
    env["PYTRAIN_TEST_METHOD"] = method
    completed = subprocess.run(
        [sys.executable, str(script)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
