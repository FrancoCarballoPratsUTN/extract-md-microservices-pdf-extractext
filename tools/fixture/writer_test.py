import unittest

from tools.fixture.objects import Name, Ref, Stream
from tools.fixture.writer import PdfWriter


class PdfWriterTest(unittest.TestCase):
    def test_added_object_is_numbered_starting_at_one(self):
        writer = PdfWriter()

        first = writer.add(Name("Catalog"))
        second = writer.add(Name("Pages"))

        self.assertEqual(first, 1)
        self.assertEqual(second, 2)

    def test_written_file_starts_with_the_pdf_header(self):
        writer = PdfWriter()

        self.assertTrue(writer.write().startswith(b"%PDF-1.7"))

    def test_written_file_ends_with_the_end_of_file_marker(self):
        writer = PdfWriter()

        self.assertTrue(writer.write().rstrip().endswith(b"%%EOF"))

    def test_xref_offset_points_at_the_start_of_its_own_object(self):
        writer = PdfWriter()
        first = writer.add(Name("Catalog"))
        second = writer.add(Name("Pages"))

        written = writer.write()

        self.assertTrue(written[writer.offset(first):].startswith(b"1 0 obj"))
        self.assertTrue(written[writer.offset(second):].startswith(b"2 0 obj"))

    def test_xref_lists_one_free_entry_for_object_zero(self):
        writer = PdfWriter()
        writer.add(Name("Catalog"))

        written = writer.write()

        self.assertIn(b"xref\n0 2\n0000000000 65535 f \n", written)

    def test_startxref_points_at_the_cross_reference_table(self):
        writer = PdfWriter()
        writer.add(Name("Catalog"))

        written = writer.write()

        start = written.rindex(b"startxref\n")
        declared = int(written[start + len(b"startxref\n"):].split()[0])
        self.assertEqual(written[declared:].startswith(b"xref"), True)

    def test_trailer_references_the_root_object_number(self):
        writer = PdfWriter()
        root = writer.add(Name("Catalog"))
        writer.set_root(root)

        written = writer.write()

        self.assertIn(b"/Root %d 0 R" % root, written)

    def test_trailer_size_counts_the_free_object_zero(self):
        writer = PdfWriter()
        writer.add(Name("Catalog"))
        writer.add(Name("Pages"))

        written = writer.write()

        self.assertIn(b"/Size 3", written)

    def test_stream_object_is_written_with_its_declared_length(self):
        writer = PdfWriter()
        number = writer.add(Stream({Name("Length"): 999}, b"12345"))

        written = writer.write()

        self.assertIn(b"/Length 5", written[writer.offset(number):])

    def test_reference_to_a_previously_added_object_is_written_as_an_indirect_reference(self):
        writer = PdfWriter()
        pages = writer.add(Name("Pages"))
        writer.add({Name("Parent"): Ref(pages)})

        written = writer.write()

        self.assertIn(b"<< /Parent 1 0 R >>", written)


if __name__ == "__main__":
    unittest.main()