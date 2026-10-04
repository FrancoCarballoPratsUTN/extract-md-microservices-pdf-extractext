import zlib

from tools.fixture.objects import Name, Stream

COMPRESSION_LEVEL = 6


class ContentBuilder:
    def __init__(self):
        self._operators = []

    def begin_text(self):
        return self._operate(b"BT")

    def end_text(self):
        return self._operate(b"ET")

    def use_font(self, name, size):
        return self._operate(b"/%s %d Tf" % (name.encode("ascii"), size))

    def move_text_origin(self, x, y):
        return self._operate(b"%d %d Td" % (x, y))

    def next_line(self):
        return self._operate(b"T*")

    def show_text(self, codes):
        return self._operate(_hexadecimal(codes) + b" Tj")

    def show_text_with_gaps(self, runs):
        parts = []
        for index, (codes, gap) in enumerate(runs):
            parts.append(_hexadecimal(codes))
            if index < len(runs) - 1:
                parts.append(b"%d" % -gap)
        return self._operate(b"[%s] TJ" % b" ".join(parts))

    def draw_image(self, name, x, y, width, height):
        return self._operate(
            b"q %d 0 0 %d %d %d cm /%s Do Q"
            % (width, height, x, y, name.encode("ascii"))
        )

    def serialize(self):
        return b" ".join(self._operators)

    def _operate(self, operator):
        self._operators.append(operator)
        return self


class ImageXObject:
    def __init__(self, width, height, pixels):
        self._width = width
        self._height = height
        self._pixels = bytes(pixels)

    def pixel_count(self):
        return len(self._pixels)

    def dictionary(self):
        return {
            Name("Type"): Name("XObject"),
            Name("Subtype"): Name("Image"),
            Name("Width"): self._width,
            Name("Height"): self._height,
            Name("ColorSpace"): Name("DeviceRGB"),
            Name("BitsPerComponent"): 8,
            Name("Filter"): Name("FlateDecode"),
        }

    def serialize(self):
        return Stream(self.dictionary(), zlib.compress(self._pixels, COMPRESSION_LEVEL)).serialize()


def image_xobject(width, height, pixels):
    return ImageXObject(width, height, pixels)


def _hexadecimal(codes):
    return b"<" + codes.hex().upper().encode("ascii") + b">"