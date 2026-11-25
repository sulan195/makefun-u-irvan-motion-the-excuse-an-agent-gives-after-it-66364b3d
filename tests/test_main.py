"""Tests for the excuse entry (main.py).

Covers the gate (1-200 UTF-8 chars, not whitespace-only), the exact
output bytes (no trailing newline), determinism, the output-dir
contract, and the 14 edge cases from Fase 2.
"""

import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main as entry


class TestLine(unittest.TestCase):
    def test_line_length(self):
        self.assertEqual(len(entry.LINE), 118)
        self.assertLessEqual(len(entry.LINE), entry.MAX_CHARS)

    def test_line_is_ascii_single_line(self):
        self.assertTrue(entry.LINE.isascii())
        self.assertNotIn("\n", entry.LINE)
        self.assertNotIn("\r", entry.LINE)
        self.assertNotIn('"', entry.LINE)
        self.assertFalse(entry.LINE.startswith('"'))
        self.assertFalse(entry.LINE.endswith('"'))

    def test_line_on_subject(self):
        self.assertIn("context window", entry.LINE)
        self.assertIn("tactical error", entry.LINE)
        self.assertTrue(entry.LINE.rstrip().endswith("tactical error."))


class TestValidate(unittest.TestCase):
    def test_accepts_line(self):
        entry.validate(entry.LINE)

    def test_accepts_one_char(self):
        entry.validate("x")

    def test_accepts_exactly_200(self):
        entry.validate("a" * 200)

    def test_accepts_non_ascii_utf8(self):
        entry.validate("café — ünïcode ✓")

    def test_rejects_empty(self):
        with self.assertRaises(ValueError):
            entry.validate("")

    def test_rejects_whitespace_only(self):
        for bad in ("   ", "\t", " \t "):
            with self.assertRaises(ValueError, msg=repr(bad)):
                entry.validate(bad)

    def test_rejects_over_200(self):
        with self.assertRaises(ValueError):
            entry.validate("a" * 201)

    def test_rejects_internal_newline(self):
        with self.assertRaises(ValueError):
            entry.validate("one\ntwo")

    def test_rejects_carriage_return(self):
        with self.assertRaises(ValueError):
            entry.validate("one\rtwo")

    def test_rejects_control_char(self):
        with self.assertRaises(ValueError):
            entry.validate("bell\x07rings")

    def test_rejects_c1_control(self):
        with self.assertRaises(ValueError):
            entry.validate("next\u0085line")

    def test_rejects_line_separator(self):
        with self.assertRaises(ValueError):
            entry.validate("one\u2028two")
        with self.assertRaises(ValueError):
            entry.validate("one\u2029two")

    def test_rejects_lone_surrogate(self):
        with self.assertRaises(ValueError):
            entry.validate("bad\ud800line")

    def test_rejects_non_string(self):
        with self.assertRaises(ValueError):
            entry.validate(123)  # type: ignore[arg-type]


class TestOutputDir(unittest.TestCase):
    def test_env_dir_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["MAKEFUN_OUTPUT_DIR"] = tmp
            try:
                self.assertEqual(entry.output_dir(), tmp)
            finally:
                del os.environ["MAKEFUN_OUTPUT_DIR"]

    def test_unset_env_falls_back(self):
        os.environ.pop("MAKEFUN_OUTPUT_DIR", None)
        self.assertEqual(entry.output_dir(), "/output")

    def test_surrounding_spaces_used_unchanged(self):
        os.environ["MAKEFUN_OUTPUT_DIR"] = " /tmp/out "
        try:
            self.assertEqual(entry.output_dir(), " /tmp/out ")
        finally:
            del os.environ["MAKEFUN_OUTPUT_DIR"]


class TestMainRun(unittest.TestCase):
    def run_main(self, env_dir):
        env = dict(os.environ)
        env["MAKEFUN_OUTPUT_DIR"] = env_dir
        proc = subprocess.run(
            [sys.executable, "main.py"],
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            env=env,
            capture_output=True,
            text=True,
        )
        return proc

    def test_writes_exact_bytes_no_trailing_newline(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = self.run_main(tmp)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            with open(os.path.join(tmp, "entry.txt"), "rb") as handle:
                data = handle.read()
            self.assertEqual(data, entry.LINE.encode("utf-8"))
            self.assertFalse(data.endswith(b"\n"))

    def test_deterministic_two_runs(self):
        with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
            self.assertEqual(self.run_main(tmp1).returncode, 0)
            self.assertEqual(self.run_main(tmp2).returncode, 0)
            with open(os.path.join(tmp1, "entry.txt"), "rb") as h1, open(
                os.path.join(tmp2, "entry.txt"), "rb"
            ) as h2:
                self.assertEqual(h1.read(), h2.read())

    def test_creates_missing_output_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            nested = os.path.join(tmp, "a", "b")
            proc = self.run_main(nested)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(os.path.isfile(os.path.join(nested, "entry.txt")))

    def test_output_path_is_file_fails(self):
        with tempfile.NamedTemporaryFile() as tmpfile:
            proc = self.run_main(tmpfile.name)
            self.assertNotEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
