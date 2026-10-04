import unittest

from tools.fixture.cmap import ToUnicodeCMap


class ToUnicodeCMapTest(unittest.TestCase):
    def test_mapping_is_emitted_as_a_two_byte_code_and_a_utf16_be_target(self):
        cmap = ToUnicodeCMap({1: "A"})

        self.assertIn(b"<0001> <0041>", cmap.serialize())

    def test_mappings_are_wrapped_in_the_begin_and_end_cmap_section(self):
        cmap = ToUnicodeCMap({1: "A"})

        serialized = cmap.serialize()

        self.assertIn(b"begincmap", serialized)
        self.assertIn(b"endcmap", serialized)

    def test_codespace_range_declares_the_full_two_byte_range(self):
        cmap = ToUnicodeCMap({1: "A"})

        self.assertIn(b"1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange", cmap.serialize())

    def test_multi_byte_rune_is_emitted_as_a_surrogate_pair(self):
        cmap = ToUnicodeCMap({7: "\U0001F600"})

        self.assertIn(b"<0007> <D83DDE00>", cmap.serialize())

    def test_latin_accented_rune_is_emitted_as_a_single_utf16_code_unit(self):
        cmap = ToUnicodeCMap({7: "ñ"})

        self.assertIn(b"<0007> <00F1>", cmap.serialize())

    def test_mapping_that_targets_a_non_ascii_rune_is_serialized_as_ascii_only(self):
        cmap = ToUnicodeCMap({7: "ñ"})

        serialized = cmap.serialize()

        serialized.decode("ascii")
        self.assertNotIn(b"\xc3\xb1", serialized)

    def test_mappings_are_emitted_in_ascending_code_order(self):
        cmap = ToUnicodeCMap({9: "B", 2: "A", 5: "C"})

        serialized = cmap.serialize()

        self.assertLess(serialized.index(b"<0002>"), serialized.index(b"<0005>"))
        self.assertLess(serialized.index(b"<0005>"), serialized.index(b"<0009>"))

    def test_more_than_one_hundred_mappings_are_split_into_several_blocks(self):
        mappings = {code: "A" for code in range(1, 151)}

        serialized = ToUnicodeCMap(mappings).serialize()

        self.assertEqual(serialized.count(b"beginbfchar"), 2)
        self.assertEqual(serialized.count(b"endbfchar"), 2)


if __name__ == "__main__":
    unittest.main()