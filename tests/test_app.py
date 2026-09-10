import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app


class AppLauncherTests(unittest.TestCase):
    def test_restarts_with_project_venv_when_started_with_system_python(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            interpreter = root / '.venv' / 'bin' / 'python'
            interpreter.parent.mkdir(parents=True)
            interpreter.touch()

            with patch.object(app, 'ROOT', root), \
                    patch.object(app.sys, 'executable', '/usr/bin/python3'), \
                    patch.object(app.os, 'execv') as execv:
                app.restart_in_project_venv()

            execv.assert_called_once_with(
                str(interpreter),
                [str(interpreter), str(root / 'app.py'), *app.sys.argv[1:]],
            )

    def test_does_not_restart_when_venv_is_already_active(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            interpreter = root / '.venv' / 'bin' / 'python'
            interpreter.parent.mkdir(parents=True)
            interpreter.touch()

            with patch.object(app, 'ROOT', root), \
                    patch.object(app.sys, 'executable', str(interpreter)), \
                    patch.object(app.os, 'execv') as execv:
                app.restart_in_project_venv()

            execv.assert_not_called()


if __name__ == '__main__':
    unittest.main()
