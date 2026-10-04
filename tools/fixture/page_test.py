import unittest

from tools.fixture.page import ContentBuilder, image_xobject


def _stream_body(serialized):
    return serialized.split(b"\nstream\n", 1)[1].rsplit(b"\nendstream", 1)[0]


class ContentBuilderTest(unittest.TestCase):
    def test_text_block_is_delimited_by_begin_and_end_text(self):
        builder = ContentBuilder()
        builder.begin_text()
        builder.end_text()

        self.assertEqual(builder.serialize(), b"BT ET")

    def test_selecting_a_font_names_the_resource_and_the_size(self):
        builder = ContentBuilder()
        builder.use_font("F1", 12)

        self.assertEqual(builder.serialize(), b"/F1 12 Tf")

    def test_moving_the_text_origin_emits_both_coordinates(self):
        builder = ContentBuilder()
        builder.move_text_origin(72, 720)

        self.assertEqual(builder.serialize(), b"72 720 Td")

    def test_showing_text_emits_two_byte_codes_as_a_hexadecimal_string(self):
        builder = ContentBuilder()
        builder.show_text(b"\x00\x01\x00\x02")

        self.assertEqual(builder.serialize(), b"<00010002> Tj")

    def test_showing_an_array_of_runs_keeps_the_numeric_gap_between_them(self):
        builder = ContentBuilder()
        builder.show_text_with_gaps([(b"\x00\x01", 120), (b"\x00\x02", 0)])

        self.assertEqual(builder.serialize(), b"[<0001> -120 <0002>] TJ")

    def test_advancing_to_the_next_line_emits_the_star_operator(self):
        builder = ContentBuilder()
        builder.next_line()

        self.assertEqual(builder.serialize(), b"T*")

    def test_drawing_an_image_wraps_the_xobject_call_in_save_and_restore(self):
        builder = ContentBuilder()
        builder.draw_image("Im0", 100, 600, 64, 64)

        self.assertEqual(builder.serialize(), b"q 64 0 0 64 100 600 cm /Im0 Do Q")

    def test_serialized_content_separates_every_operator_with_one_space(self):
        builder = ContentBuilder()
        builder.begin_text()
        builder.use_font("F1", 12)
        builder.move_text_origin(72, 720)
        builder.end_text()

        self.assertEqual(builder.serialize(), b"BT /F1 12 Tf 72 720 Td ET")


class ImageXObjectTest(unittest.TestCase):
    def test_image_declares_its_dimensions_color_space_and_filter(self):
        serialized = image_xobject(8, 4, b"\x00" * 96).serialize()

        self.assertIn(b"/Type /XObject", serialized)
        self.assertIn(b"/Subtype /Image", serialized)
        self.assertIn(b"/Width 8", serialized)
        self.assertIn(b"/Height 4", serialized)
        self.assertIn(b"/ColorSpace /DeviceRGB", serialized)
        self.assertIn(b"/BitsPerComponent 8", serialized)
        self.assertIn(b"/Filter /FlateDecode", serialized)

    def test_image_declares_a_length_matching_the_bytes_it_actually_carries(self):
        serialized = image_xobject(8, 4, bytes(range(96))).serialize()

        self.assertIn(b"/Length %d" % len(_stream_body(serialized)), serialized)

    def test_image_stream_body_is_smaller_than_the_raw_pixels(self):
        pixels = bytes(96)

        body = _stream_body(image_xobject(8, 4, pixels).serialize())

        self.assertLess(len(body), len(pixels))

    def test_image_reports_how_many_bytes_it_was_built_from(self):
        self.assertEqual(image_xobject(8, 4, bytes(96)).pixel_count(), 96)

    def test_image_serializes_identically_for_identical_pixels(self):
        self.assertEqual(
            image_xobject(8, 4, bytes(range(96))).serialize(),
            image_xobject(8, 4, bytes(range(96))).serialize(),
        )

    def test_different_pixels_produce_different_serialized_bytes(self):
        self.assertNotEqual(
            image_xobject(8, 4, bytes(96)).serialize(),
            image_xobject(8, 4, bytes([1]) + bytes(95)).serialize(),
        )


if __name__ == "__main__":
    unittest.main()