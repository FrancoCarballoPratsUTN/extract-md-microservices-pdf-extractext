import unittest

from tools.fixture.objects import Name, Ref, Stream, serialize


class SerializeTest(unittest.TestCase):
    def test_name_serializes_as_a_slash_prefixed_token(self):
        self.assertEqual(serialize(Name("Type")), b"/Type")

    def test_reference_serializes_as_object_number_generation_and_keyword(self):
        self.assertEqual(serialize(Ref(12, 0)), b"12 0 R")

    def test_reference_defaults_to_generation_zero(self):
        self.assertEqual(serialize(Ref(7)), b"7 0 R")

    def test_byte_sequence_serializes_as_uppercase_hexadecimal_string(self):
        self.assertEqual(serialize(b"\x00\x01\xab"), b"<0001AB>")

    def test_dictionary_serializes_with_slash_prefixed_keys(self):
        self.assertEqual(serialize({Name("Type"): Name("Page")}), b"<< /Type /Page >>")

    def test_array_serializes_values_separated_by_single_spaces(self):
        self.assertEqual(serialize([0, 0, 612, 792]), b"[0 0 612 792]")

    def test_integer_serializes_without_decimal_point(self):
        self.assertEqual(serialize(250), b"250")

    def test_boolean_serializes_as_pdf_keyword(self):
        self.assertEqual(serialize(True), b"true")

    def test_string_serializes_as_parenthesized_literal(self):
        self.assertEqual(serialize("Adobe"), b"(Adobe)")

    def test_none_serializes_as_the_null_keyword(self):
        self.assertEqual(serialize(None), b"null")

    def test_unsupported_type_is_rejected_instead_of_guessed(self):
        with self.assertRaises(TypeError):
            serialize(object())

    def test_stream_declares_its_own_length(self):
        stream = Stream({Name("Type"): Name("XObject")}, b"payload")

        self.assertEqual(stream.serialize(), b"<< /Type /XObject /Length 7 >>\nstream\npayload\nendstream")

    def test_stream_keeps_the_caller_dictionary_untouched(self):
        dictionary = {Name("Type"): Name("XObject")}

        Stream(dictionary, b"payload")

        self.assertEqual(dictionary, {Name("Type"): Name("XObject")})


if __name__ == "__main__":
    unittest.main()