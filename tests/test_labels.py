import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from soundboard import pretty_label


class TestPrettyLabel(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(pretty_label("shaco.mp3"), "Shaco")

    def test_dashes_to_spaces_title_case(self):
        self.assertEqual(pretty_label("lulu-gosto-roxo.mp3"), "Lulu Gosto Roxo")

    def test_strips_download_hash(self):
        self.assertEqual(pretty_label("ola-macaquito-messi_FfqSSjF.mp3"), "Ola Macaquito Messi")

    def test_strips_hash_then_tool_suffix(self):
        self.assertEqual(
            pretty_label("dark-souls-you-died-sound-effect_hm5sYFG.mp3"),
            "Dark Souls You Died",
        )

    def test_strips_mp3cut(self):
        self.assertEqual(pretty_label("volibear-morrendo-mp3cut.mp3"), "Volibear Morrendo")

    def test_keeps_lowercase_only_suffix(self):
        # "beta" é minúsculo puro, não é hash -> não remove
        self.assertEqual(
            pretty_label("brutal-acabou-pro-beta-globo.mp3"),
            "Brutal Acabou Pro Beta Globo",
        )

    def test_accepts_full_path(self):
        self.assertEqual(pretty_label("/home/cristian/Music/shaco.mp3"), "Shaco")

    def test_uppercase_extension(self):
        self.assertEqual(pretty_label("SHACO.MP3"), "Shaco")

    def test_empty_after_strip_falls_back(self):
        self.assertEqual(pretty_label("-mp3cut.mp3"), "Mp3Cut")
