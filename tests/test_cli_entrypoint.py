import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from app.main import main


class CliEntrypointTest(unittest.TestCase):
    def test_cli_single_client_path_works(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()

        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(["--client", "demo-client"])

        self.assertEqual(exit_code, 0)
        self.assertIn("Client: BrightPath Creative", stdout.getvalue())
        self.assertEqual(stderr.getvalue(), "")

    def test_cli_all_clients_path_works(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()

        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(["--all-clients"])

        self.assertEqual(exit_code, 0)
        self.assertIn("Clients attempted: 1", stdout.getvalue())
        self.assertIn("Clients succeeded: 1", stdout.getvalue())
        self.assertEqual(stderr.getvalue(), "")

    def test_cli_exit_behavior_is_correct(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()

        with tempfile.TemporaryDirectory() as tmpdir:
            missing_root = Path(tmpdir) / "missing-clients"
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(["--all-clients", "--configs-root", str(missing_root)])

        self.assertEqual(exit_code, 1)
        self.assertIn("Configs root not found", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
