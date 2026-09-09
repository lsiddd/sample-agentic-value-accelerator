"""Check reference imports in the layout used by Dockerfile.agentcore, without inference."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def check_reference(fsi_root: Path) -> None:
    with tempfile.TemporaryDirectory(prefix='ava-import-check-') as temporary:
        root = Path(temporary)
        package = root / 'use_cases' / 'customer_service'
        shutil.copytree(fsi_root / 'use_cases/customer_service/src/strands', package)
        (root / 'use_cases/__init__.py').touch()
        env = {**os.environ, 'ENABLE_TRACING': 'false',
               'PYTHONPATH': os.pathsep.join([str(root), str(fsi_root / 'foundations/src')])}
        subprocess.run([
            sys.executable, '-c',
            "from use_cases.customer_service import CustomerServiceOrchestrator; print('Reference import OK')",
        ], cwd=root, env=env, check=True, timeout=60)


if __name__ == '__main__':
    check_reference(Path(sys.argv[1]).resolve())
