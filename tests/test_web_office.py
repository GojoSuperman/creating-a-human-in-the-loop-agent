import shutil
import subprocess

import pytest


@pytest.mark.skipif(not shutil.which("node"), reason="node 없음")
def test_office_replay_logic():
    out = subprocess.run(["node", "tests/web/office.test.mjs"], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr + out.stdout


@pytest.mark.skipif(not shutil.which("node"), reason="node 없음")
def test_paths_avoid_furniture():
    out = subprocess.run(["node", "tests/web/path.test.mjs"], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr + out.stdout


@pytest.mark.skipif(not shutil.which("node"), reason="node 없음")
def test_bubbles_do_not_overlap():
    out = subprocess.run(["node", "tests/web/bubbles.test.mjs"], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr + out.stdout
