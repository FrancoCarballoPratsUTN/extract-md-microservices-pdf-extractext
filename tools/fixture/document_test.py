import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.fixture.document import REFERENCE_PROFILE, ReferenceDocument
from tools.gate.wordmatch import match_ratio


class ReferenceDocumentTest(unittest.TestCase):
    def test_document_declares_the_number_of_pages_the_profile_asks_for(self):
        document = ReferenceDocument({"pages": 7})

        self.assertEqual(document.page_count(), 7)

    def test_pdf_page_tree_carries_one_kid_per_page(self):
        document = ReferenceDocument({"pages": 7})

        self.assertIn(b"/Count 7", document.write())

    def test_document_is_readable_by_pdftotext(self):
        document = ReferenceDocument({"pages": 2, "characters_per_page": 400})

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "out.pdf"
            path.write_bytes(document.write())
            subprocess.run(
                ["pdftotext", str(path), str(Path(directory) / "out.txt")],
                check=True,
            )
            extracted = (Path(directory) / "out.txt").read_text()

        self.assertEqual(match_ratio(document.expected_text(), extracted), 1.0)

    def test_every_generated_word_survives_the_round_trip(self):
        document = ReferenceDocument({"pages": 3, "characters_per_page": 900})
        document.write()

        extracted = pdftotext(document)

        self.assertGreater(match_ratio(document.expected_text(), extracted), 0.99)

    def test_every_page_contributes_text_to_the_extraction(self):
        document = ReferenceDocument({"pages": 4, "characters_per_page": 600})

        extracted = pdftotext(document)

        self.assertEqual(extracted.count("\f"), 4)

    def test_generated_text_uses_accents_so_utf8_decoding_is_exercised(self):
        document = ReferenceDocument({"pages": 1, "characters_per_page": 900})

        extracted = pdftotext(document)

        self.assertTrue(any(character in extracted for character in "áéíóúñÁÉÍÓÚÑü"))

    def test_generated_text_uses_both_plain_and_kerned_show_text_operators(self):
        document = ReferenceDocument({"pages": 1, "characters_per_page": 900})

        content = document.page_content(0)

        self.assertIn(b" Tj", content)
        self.assertIn(b" TJ", content)

    def test_content_stream_is_flate_compressed(self):
        document = ReferenceDocument({"pages": 1, "characters_per_page": 200})

        self.assertNotIn(b" Tj", document.write())

    def test_images_are_referenced_from_the_page_resource_dictionary(self):
        document = ReferenceDocument({"pages": 1, "distinct_images": 3, "image_draws": 3})

        self.assertIn(b"/XObject <<", document.write())

    def test_the_same_image_object_is_reused_by_several_pages(self):
        document = ReferenceDocument({"pages": 2, "distinct_images": 2, "image_draws": 6})

        self.assertEqual(document.distinct_image_count(), 2)

    def test_document_counts_one_flate_stream_per_page_and_per_image_and_one_cmap(self):
        document = ReferenceDocument({"pages": 250, "distinct_images": 1166})

        self.assertEqual(document.flate_stream_count(), 250 + 1166 + 1)

    def test_every_flate_stream_counted_by_the_model_is_present_in_the_file(self):
        document = ReferenceDocument({"pages": 20, "distinct_images": 11})

        self.assertEqual(document.write().count(b"/Filter /FlateDecode"), document.flate_stream_count())

    def test_document_reports_how_many_image_draws_it_issued(self):
        document = ReferenceDocument({"pages": 10, "distinct_images": 5, "image_draws": 55})

        self.assertEqual(document.image_draw_count(), 55)

    def test_reference_profile_totals_the_described_number_of_images(self):
        document = ReferenceDocument(REFERENCE_PROFILE)

        self.assertEqual(document.image_draw_count(), 5563)

    def test_reference_profile_yields_the_described_number_of_text_characters(self):
        document = ReferenceDocument(REFERENCE_PROFILE)

        self.assertLess(abs(document.character_count() - 709803) / 709803, 0.01)

    def test_reference_profile_yields_the_described_number_of_flate_streams(self):
        self.assertEqual(REFERENCE_PROFILE["distinct_images"], 1417 - 250 - 1)

    def test_reference_profile_decompresses_to_about_twenty_five_megabytes(self):
        document = ReferenceDocument(REFERENCE_PROFILE)

        self.assertLess(abs(document.decompressed_bytes() - 25 * 1024 * 1024) / (25 * 1024 * 1024), 0.15)

    def test_generated_file_is_of_the_same_order_of_magnitude_as_the_reference(self):
        document = ReferenceDocument(REFERENCE_PROFILE)

        self.assertLess(len(document.write()), 12 * 1024 * 1024)

    def test_generation_is_deterministic(self):
        profile = {"pages": 3, "distinct_images": 4, "image_draws": 7, "characters_per_page": 300}

        self.assertEqual(ReferenceDocument(profile).write(), ReferenceDocument(profile).write())


class PdftotextPreconditionTest(unittest.TestCase):
    def test_gate_fails_with_a_clear_message_when_pdftotext_is_absent(self):
        self.assertIsNotNone(
            shutil.which("pdftotext"),
            "pdftotext (poppler-utils) es el oráculo del gate de 70%",
        )


def pdftotext(document):
    if shutil.which("pdftotext") is None:
        raise AssertionError("pdftotext (poppler-utils) es el oráculo del gate de 70%")
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "out.pdf"
        path.write_bytes(document.write())
        subprocess.run(
            ["pdftotext", "-layout", str(path), str(Path(directory) / "out.txt")],
            check=True,
        )
        return (Path(directory) / "out.txt").read_text()


if __name__ == "__main__":
    unittest.main()