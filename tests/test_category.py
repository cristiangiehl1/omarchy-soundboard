import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from soundboard import detect_category, hex_to_rgb


class TestDetectCategory(unittest.TestCase):
    def test_games(self):
        self.assertEqual(detect_category("league-of-legends-first-blood-sound.mp3")[0], "Games")
        self.assertEqual(detect_category("shaco.mp3")[0], "Games")

    def test_anime(self):
        self.assertEqual(detect_category("kurapika-vazio-indescritivel.mp3")[0], "Anime")

    def test_memes(self):
        self.assertEqual(detect_category("risada-cariani-meme.mp3")[0], "Memes")
        self.assertEqual(detect_category("megatron-me-da-o-cu.mp3")[0], "Memes")

    def test_music(self):
        self.assertEqual(detect_category("when-i-met-you-in-the-summer.mp3")[0], "Música")

    def test_default(self):
        self.assertEqual(detect_category("algo-aleatorio-xyz.mp3"), ("Outros", "#c792ff", "other"))

    def test_returns_triple(self):
        cat, color, slug = detect_category("shaco.mp3")
        self.assertEqual((cat, color, slug), ("Games", "#00f0ff", "games"))


class TestHexToRgb(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(hex_to_rgb("#ffffff"), (1.0, 1.0, 1.0))
        self.assertEqual(hex_to_rgb("#000000"), (0.0, 0.0, 0.0))

    def test_cyan(self):
        r, g, b = hex_to_rgb("#00f0ff")
        self.assertAlmostEqual(r, 0.0)
        self.assertAlmostEqual(g, 240 / 255)
        self.assertAlmostEqual(b, 1.0)


if __name__ == "__main__":
    unittest.main()
