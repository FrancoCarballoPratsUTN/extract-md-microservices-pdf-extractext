from tools.fixture.objects import Name, Ref, serialize

HEADER = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n"


class PdfWriter:
    def __init__(self):
        self._objects = []
        self._offsets = []
        self._root = None

    def add(self, value):
        self._objects.append(value)
        self._offsets.append(0)
        return len(self._objects)

    def set_root(self, number):
        self._root = number

    def offset(self, number):
        return self._offsets[number - 1]

    def write(self):
        output = bytearray(HEADER)
        for number, value in enumerate(self._objects, start=1):
            self._offsets[number - 1] = len(output)
            output += b"%d 0 obj\n" % number
            output += serialize(value)
            output += b"\nendobj\n"
        start = len(output)
        output += b"xref\n0 %d\n" % (len(self._objects) + 1)
        output += b"0000000000 65535 f \n"
        for offset in self._offsets:
            output += b"%010d 00000 n \n" % offset
        output += b"trailer\n" + serialize(self._trailer()) + b"\nstartxref\n%d\n%%%%EOF\n" % start
        return bytes(output)

    def _trailer(self):
        trailer = {Name("Size"): len(self._objects) + 1}
        if self._root is not None:
            trailer[Name("Root")] = Ref(self._root)
        return trailer