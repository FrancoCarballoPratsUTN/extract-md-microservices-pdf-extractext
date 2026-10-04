import unittest

from tools.gate.wordmatch import match_ratio, words


class WordsTest(unittest.TestCase):
    def test_text_is_split_on_whitespace(self):
        self.assertEqual(words("hola mundo"), ["hola", "mundo"])

    def test_case_is_ignored(self):
        self.assertEqual(words("Hola MUNDO"), ["hola", "mundo"])

    def test_punctuation_is_not_part_of_a_word(self):
        self.assertEqual(words("Hola, mundo."), ["hola", "mundo"])

    def test_accents_are_preserved_because_they_are_word_content(self):
        self.assertEqual(words("La palabras"), ["la", "palabras"])

    def test_empty_text_yields_no_words(self):
        self.assertEqual(words("   \n\t "), [])


class MatchRatioTest(unittest.TestCase):
    def test_identical_text_matches_every_word(self):
        self.assertEqual(match_ratio("hola mundo", "hola mundo"), 1.0)

    def test_disjoint_text_matches_nothing(self):
        self.assertEqual(match_ratio("hola mundo", "adios cosmos"), 0.0)

    def test_ratio_is_measured_against_the_expected_word_set(self):
        self.assertEqual(match_ratio("hola mundo", "hola"), 0.5)

    def test_ratio_is_measured_against_the_expected_word_set_when_actual_is_longer(self):
        self.assertEqual(match_ratio("hola", "hola mundo"), 1.0)

    def test_repetitions_in_the_actual_text_do_not_earn_extra_credit(self):
        self.assertEqual(match_ratio("hola", "hola hola hola"), 1.0)

    def test_repetitions_missing_from_the_actual_text_count_against_the_ratio(self):
        self.assertEqual(match_ratio("hola hola", "hola"), 0.5)

    def test_text_that_replaces_a_word_with_another_one_is_penalized(self):
        self.assertEqual(match_ratio("hola mundo", "hola hola"), 0.5)

    def test_half_the_expected_words_missing_halves_the_ratio(self):
        self.assertEqual(match_ratio("uno dos tres cuatro", "uno dos"), 0.5)

    def test_punctuation_and_case_differences_still_match(self):
        self.assertEqual(match_ratio("Hola, mundo.", "HOLA MUNDO"), 1.0)

    def test_empty_expected_text_matches_everything(self):
        self.assertEqual(match_ratio("", "hola"), 1.0)

    def test_empty_actual_text_matches_nothing(self):
        self.assertEqual(match_ratio("hola", ""), 0.0)


if __name__ == "__main__":
    unittest.main()