import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from soundboard import scan_sounds


class TestScanSounds(unittest.TestCase):
    def test_empty_or_missing_dir(self):
        self.assertEqual(scan_sounds("/nao/existe/aqui"), [])

    def test_finds_and_sorts_mp3(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ["zeta.mp3", "alpha.mp3", "not-audio.txt"]:
                open(os.path.join(d, name), "w").close()
            result = scan_sounds(d)
            labels = [label for label, _ in result]
            paths = [path for _, path in result]
            self.assertEqual(labels, ["Alpha", "Zeta"])
            self.assertTrue(all(os.path.isabs(p) for p in paths))
            self.assertTrue(all(p.endswith(".mp3") for p in paths))

    def test_case_insensitive_extension(self):
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, "Loud.MP3"), "w").close()
            result = scan_sounds(d)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0][0], "Loud")
