import shutil
import subprocess
from pathlib import Path

import pytest

JS = sorted(Path("web/src").glob("*.js"))


@pytest.mark.skipif(not shutil.which("node"), reason="node 없음")
@pytest.mark.parametrize("path", JS, ids=lambda p: p.name)
def test_js_parses_as_module(path, tmp_path):
    mjs = tmp_path / (path.stem + ".mjs")
    mjs.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    subprocess.run(["node", "--check", str(mjs)], check=True)
