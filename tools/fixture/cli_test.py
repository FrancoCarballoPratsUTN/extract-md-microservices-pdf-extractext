import pathlib
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO

from tools.fixture import cli


class CliTest(unittest.TestCase):
    def test_writes_a_pdf_to_the_requested_path(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "ref.pdf"

            exit_code = run(cli.main, ["--out", str(path), "--pages", "1"])

            self.assertEqual(exit_code, 0)
            self.assertTrue(path.read_bytes().startswith(b"%PDF-"))

    def test_reports_the_size_it_produced(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "ref.pdf"
            captured = StringIO()

            with redirect_stdout(captured):
                run(cli.main, ["--out", str(path), "--pages", "1"])

            self.assertIn(str(path.stat().st_size), captured.getvalue())

    def test_reports_the_characteristics_it_produced(self):
        with tempfile.TemporaryDirectory() as directory:
            captured = StringIO()

            with redirect_stdout(captured):
                run(cli.main, ["--out", str(directory) + "/ref.pdf", "--pages", "3"])

            self.assertIn("pages=3", captured.getvalue())
            self.assertIn("flate_streams=", captured.getvalue())
            self.assertIn("image_draws=", captured.getvalue())
            self.assertIn("decompressed=", captured.getvalue())

    def test_profile_flags_are_applied_to_the_generated_document(self):
        with tempfile.TemporaryDirectory() as directory:
            captured = StringIO()

            with redirect_stdout(captured):
                run(cli.main, [
                    "--out", directory + "/ref.pdf",
                    "--pages", "2",
                    "--distinct-images", "5",
                    "--image-draws", "9",
                    "--characters-per-page", "250",
                ])

            self.assertIn("image_draws=9", captured.getvalue())
            self.assertIn("flate_streams=8", captured.getvalue())

    def test_missing_output_path_is_reported_instead_of_crashing(self):
        self.assertEqual(run(cli.main, ["--pages", "1"]), 2)

    def test_unknown_flag_is_reported_instead_of_being_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(run(cli.main, ["--out", directory + "/x.pdf", "--nope"]), 2)

    def test_non_numeric_value_is_reported_instead_of_crashing(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(run(cli.main, ["--out", directory + "/x.pdf", "--pages", "dos"]), 2)


def run(main, argv):
    try:
        with redirect_stderr(StringIO()):
            return main(argv)
    except SystemExit as exit:
        return exit.code


if __name__ == "__main__":
    unittest.main()