import zlib

from tools.fixture.cmap import ToUnicodeCMap
from tools.fixture.objects import Name, Ref, Stream
from tools.fixture.page import ContentBuilder, image_xobject
from tools.fixture.text import JOINER, TextCorpus, vocabulary
from tools.fixture.writer import PdfWriter

REFERENCE_PROFILE = {
    "pages": 250,
    "distinct_images": 1166,
    "image_draws": 5563,
    "characters_per_page": 2839,
    "image_side": 82,
}

_DEFAULTS = {
    "pages": 1,
    "distinct_images": 0,
    "image_draws": 0,
    "characters_per_page": 0,
    "image_side": 82,
}

MEDIA_BOX = [0, 0, 612, 792]
FONT_SIZE = 12
LINE_HEIGHT = 14
LINE_GAP = 20
MARGIN_X = 72
TOP_Y = 730
IMAGES_PER_ROW = 6
IMAGE_SIZE = 24
IMAGE_GAP = 8
IMAGE_TOP = 120
NOISE_BLOCK = 1024


class ReferenceDocument:
    def __init__(self, profile=None):
        self._profile = dict(_DEFAULTS)
        self._profile.update(profile or {})
        self._corpus = TextCorpus(vocabulary())
        self._writer = None
        self._texts_cache = None

    def page_count(self):
        return self._profile["pages"]

    def distinct_image_count(self):
        return self._profile["distinct_images"]

    def image_draw_count(self):
        return self._profile["image_draws"]

    def flate_stream_count(self):
        return self.page_count() + self.distinct_image_count() + 1

    def character_count(self):
        return sum(len(text) for text in self._texts())

    def decompressed_bytes(self):
        content = sum(len(self._content(index).serialize()) for index in range(self.page_count()))
        images = self._profile["distinct_images"] * _image_size(self._profile["image_side"])
        cmap = len(ToUnicodeCMap(self._corpus.cmap_mappings()).serialize())
        return content + images + cmap

    def expected_text(self):
        return "\n".join(self._texts())

    def page_content(self, index):
        return self._content(index).serialize()

    def write(self):
        if self._writer is None:
            self._writer = self._build()
        return self._writer.write()

    def _texts(self):
        if self._texts_cache is None:
            self._texts_cache = [
                self._corpus.page_text(index, self._profile["characters_per_page"])
                for index in range(self.page_count())
            ]
        return self._texts_cache

    def _content(self, index):
        return _PageContent(self._corpus, self._draws_on(index)).build(self._texts()[index])

    def _draws_on(self, index):
        draws = self.image_draw_count() // self.page_count()
        if index < self.image_draw_count() % self.page_count():
            draws += 1
        return draws

    def _build(self):
        writer = PdfWriter()
        pages = {}
        pages_number = writer.add(pages)
        font = _font(writer, self._corpus)
        images = [
            _image(writer, index, self._profile["image_side"])
            for index in range(self.distinct_image_count())
        ]
        kids = [
            self._page(writer, pages_number, font, images, index)
            for index in range(self.page_count())
        ]
        pages[Name("Type")] = Name("Pages")
        pages[Name("Kids")] = kids
        pages[Name("Count")] = self.page_count()
        catalog = writer.add({Name("Type"): Name("Catalog"), Name("Pages"): Ref(pages_number)})
        writer.set_root(catalog)
        return writer

    def _page(self, writer, pages_number, font, images, index):
        content = writer.add(
            Stream(
                {Name("Filter"): Name("FlateDecode")},
                zlib.compress(self._content(index).serialize()),
            )
        )
        resources = {Name("Font"): {Name("F1"): Ref(font)}}
        draws = self._draws_on(index)
        if draws and images:
            resources[Name("XObject")] = {
                Name("Im%d" % slot): images[(index * IMAGES_PER_ROW + slot) % len(images)]
                for slot in range(min(draws, len(images)))
            }
        return Ref(writer.add({
            Name("Type"): Name("Page"),
            Name("Parent"): Ref(pages_number),
            Name("MediaBox"): MEDIA_BOX,
            Name("Resources"): resources,
            Name("Contents"): Ref(content),
        }))


class _PageContent:
    def __init__(self, corpus, draws):
        self._corpus = corpus
        self._draws = draws

    def build(self, text):
        builder = ContentBuilder()
        for line_number, line in enumerate(_lines(text)):
            self._draw_line(builder, line, line_number)
        for slot in range(self._draws):
            self._draw_image(builder, slot)
        return builder

    def _draw_line(self, builder, line, line_number):
        y = TOP_Y - line_number * LINE_HEIGHT
        builder.begin_text()
        builder.use_font("F1", FONT_SIZE)
        builder.move_text_origin(MARGIN_X, y)
        if line_number % 3 == 2:
            head, tail = _split_inside_a_word(line)
            builder.show_text_with_gaps([
                (self._corpus.encode(head), LINE_GAP),
                (self._corpus.encode(tail), 0),
            ])
        else:
            builder.show_text(self._corpus.encode(line))
        builder.end_text()

    def _draw_image(self, builder, slot):
        column = slot % IMAGES_PER_ROW
        row = slot // IMAGES_PER_ROW
        x = MARGIN_X + column * (IMAGE_SIZE + IMAGE_GAP)
        y = IMAGE_TOP + row * (IMAGE_SIZE + IMAGE_GAP)
        builder.draw_image("Im%d" % (slot % IMAGES_PER_ROW), x, y, IMAGE_SIZE, IMAGE_SIZE)


def _lines(text):
    return [line for line in text.split("\n") if line]


def _split_inside_a_word(line):
    middle = len(line) // 2
    boundary = line.find(JOINER, middle)
    if boundary < 0:
        boundary = len(line)
    cut = boundary + 1 + max(1, (len(line) - boundary - 1) // 2)
    return line[:cut], line[cut:]


def _image(writer, index, side):
    return Ref(writer.add(image_xobject(side, side, _pixels(side, index))))


def _image_size(side):
    return side * side * 3


def _pixels(side, seed):
    total = _image_size(side)
    block = _noise(seed)
    repeats = -(-total // len(block))
    start = seed % len(block)
    return (block[start:] + block * repeats)[:total]


def _noise(seed):
    state = (seed + 1) * 2654435761 & 0xFFFFFFFF
    output = bytearray(NOISE_BLOCK)
    for index in range(NOISE_BLOCK):
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        output[index] = (state >> 16) & 0xFF
    return bytes(output)


def _font(writer, corpus):
    cmap = writer.add(
        Stream(
            {Name("Filter"): Name("FlateDecode")},
            zlib.compress(ToUnicodeCMap(corpus.cmap_mappings()).serialize()),
        )
    )
    descriptor = writer.add({
        Name("Type"): Name("FontDescriptor"),
        Name("FontName"): Name("FixtureSans"),
        Name("Flags"): 4,
        Name("FontBBox"): [0, 0, 1000, 1000],
        Name("ItalicAngle"): 0,
        Name("Ascent"): 800,
        Name("Descent"): -200,
        Name("CapHeight"): 700,
        Name("StemV"): 80,
    })
    descendant = writer.add({
        Name("Type"): Name("Font"),
        Name("Subtype"): Name("CIDFontType2"),
        Name("BaseFont"): Name("FixtureSans"),
        Name("CIDSystemInfo"): {
            Name("Registry"): "Adobe",
            Name("Ordering"): "Identity",
            Name("Supplement"): 0,
        },
        Name("FontDescriptor"): Ref(descriptor),
        Name("DW"): 500,
    })
    return writer.add({
        Name("Type"): Name("Font"),
        Name("Subtype"): Name("Type0"),
        Name("BaseFont"): Name("FixtureSans"),
        Name("Encoding"): Name("Identity-H"),
        Name("DescendantFonts"): [Ref(descendant)],
        Name("ToUnicode"): Ref(cmap),
    })