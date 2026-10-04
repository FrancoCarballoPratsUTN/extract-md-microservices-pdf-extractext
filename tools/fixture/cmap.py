BLOCK_SIZE = 100


class ToUnicodeCMap:
    def __init__(self, mappings):
        self._mappings = dict(mappings)

    def serialize(self):
        lines = [
            "/CIDInit /ProcSet findresource begin",
            "12 dict begin",
            "begincmap",
            "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def",
            "/CMapName /Adobe-Identity-UCS def",
            "/CMapType 2 def",
            "1 begincodespacerange",
            "<0000> <FFFF>",
            "endcodespacerange",
        ]
        for block in _blocks(self._mappings):
            lines.append("%d beginbfchar" % len(block))
            lines.extend("<%04X> <%s>" % (code, _utf16be(text)) for code, text in block)
            lines.append("endbfchar")
        lines.extend(["endcmap", "CMapName currentdict /CMap defineresource pop", "end", "end"])
        return "\n".join(lines).encode("ascii")


def _blocks(mappings):
    ordered = sorted(mappings.items())
    for start in range(0, len(ordered), BLOCK_SIZE):
        yield ordered[start:start + BLOCK_SIZE]


def _utf16be(text):
    return text.encode("utf-16-be").hex().upper()