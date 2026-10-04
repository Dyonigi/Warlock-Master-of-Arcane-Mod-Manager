#!/usr/bin/env python3
"""Convert Warlock TXML binv2.0 <-> XML (Python 3)."""

from __future__ import annotations

import io
import struct
import xml.etree.ElementTree as ET
from typing import BinaryIO, Dict, List, Tuple


XML_INDENT = "  "
TXML_HEADER = b"txml binv2.0"
TXML_HEADER_UNKNOWN = b"\xff" * 4
TXML_NULL_SPACER = b"\0" * 16

TXML_TYPE_DESCS_FROM_I = {
    0: ("integer", [("I", "value")]),
    1: ("float", [("f", "value")]),
    2: ("string", [("I", "value")]),
    3: ("bool", [("?", "value")]),
    4: ("long", [("Q", "value")]),
    5: ("2d_point_i", [("I", "x"), ("I", "y")]),
    6: ("2d_point_f", [("f", "x"), ("f", "y")]),
    7: ("3d_point_f", [("f", "x"), ("f", "y"), ("f", "z")]),
    8: ("color", [("B", "r"), ("B", "g"), ("B", "b"), ("B", "a")]),
    9: ("byte_array", [("I", "value")]),
    10: ("size", [("I", "width"), ("I", "height")]),
    11: ("rectangle", [("I", "x"), ("I", "y"), ("I", "width"), ("I", "height")]),
    12: ("short", [("H", "value")]),
}
TXML_TYPE_DESCS_FROM_STR = {
    type_str: (type_i, attrs) for type_i, (type_str, attrs) in TXML_TYPE_DESCS_FROM_I.items()
}


def is_txml(data: bytes) -> bool:
    return data.startswith(TXML_HEADER)


def _read_unpack(fd: BinaryIO, fmt: str):
    return struct.unpack("<" + fmt, fd.read(struct.calcsize(fmt)))


def _decode_string(raw: bytes) -> str:
    return raw.decode("latin-1")


def _encode_string(s: str) -> bytes:
    return s.encode("latin-1")


def _read_txml_value_node_attrs(fd: BinaryIO, itos: List[str]) -> Tuple[str, str]:
    type_i = _read_unpack(fd, "I")[0]
    if type_i not in TXML_TYPE_DESCS_FROM_I:
        raise ValueError(f"Unknown TXML type {type_i} at offset 0x{fd.tell():X}")
    type_str, attrs = TXML_TYPE_DESCS_FROM_I[type_i]
    if type_str == "string":
        string_index = _read_unpack(fd, attrs[0][0])[0]
        xml_attrs_str = f"value='{_xml_escape(itos[string_index])}'"
    elif type_str == "byte_array":
        array_length = _read_unpack(fd, attrs[0][0])[0]
        data = _read_unpack(fd, "B" * array_length) if array_length else ()
        byte_string = " ".join(f"{c:02X}" for c in data)
        xml_attrs_str = f"value='{byte_string}'"
    else:
        xml_attrs = []
        for pack_fmt, attr_name in attrs:
            val = _read_unpack(fd, pack_fmt)[0]
            if pack_fmt == "B":
                xml_attrs.append(f"{attr_name}='{val:02X}'")
            elif pack_fmt == "?":
                xml_attrs.append(f"{attr_name}='{1 if val else 0}'")
            else:
                xml_attrs.append(f"{attr_name}='{val}'")
        xml_attrs_str = " ".join(xml_attrs)
    return type_str, xml_attrs_str


def _xml_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("'", "&apos;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _write_xml_value_node(fd: BinaryIO, itos: List[str], tab_level: int, out: io.StringIO) -> None:
    name = itos[_read_unpack(fd, "I")[0]]
    type_str, attrs_str = _read_txml_value_node_attrs(fd, itos)
    indent = tab_level * XML_INDENT
    out.write(f"{indent}<{name} type='{type_str}' {attrs_str}/>\n")


def _write_xml_node_attr(fd: BinaryIO, itos: List[str], out: io.StringIO) -> None:
    attr = itos[_read_unpack(fd, "I")[0]]
    value = itos[_read_unpack(fd, "I")[0]]
    if attr != "xmlns:xsi" and not attr.startswith("xsi:"):
        out.write(f" {attr}='{_xml_escape(value)}'")


def _write_xml_node(fd: BinaryIO, itos: List[str], tab_level: int, out: io.StringIO) -> None:
    name = itos[_read_unpack(fd, "I")[0]]
    indent = tab_level * XML_INDENT
    out.write(f"{indent}<{name}")
    nr_node_attrs = _read_unpack(fd, "I")[0]
    for _ in range(nr_node_attrs):
        _write_xml_node_attr(fd, itos, out)
    out.write(">\n")
    nr_value_nodes = _read_unpack(fd, "I")[0]
    for _ in range(nr_value_nodes):
        _write_xml_value_node(fd, itos, tab_level + 1, out)
    nr_subnodes = _read_unpack(fd, "I")[0]
    for _ in range(nr_subnodes):
        _write_xml_node(fd, itos, tab_level + 1, out)
    out.write(f"{indent}</{name}>\n")


def txml_to_xml_string(data: bytes) -> str:
    fd = io.BytesIO(data)
    header = fd.read(len(TXML_HEADER))
    if header != TXML_HEADER:
        raise ValueError("Not a TXML binv2.0 file")
    fd.read(len(TXML_HEADER_UNKNOWN))
    spacer = fd.read(len(TXML_NULL_SPACER))
    if spacer != TXML_NULL_SPACER:
        raise ValueError("Unexpected TXML header spacer")
    nr_strings = _read_unpack(fd, "I")[0]
    strings_len = _read_unpack(fd, "I")[0]
    record_len = 8
    strings_blob_offset = fd.tell() + nr_strings * record_len
    itos: List[str] = []
    for _ in range(nr_strings):
        string_offset = _read_unpack(fd, "I")[0]
        string_size = _read_unpack(fd, "I")[0]
        next_off = fd.tell()
        fd.seek(strings_blob_offset + string_offset)
        itos.append(_decode_string(fd.read(string_size)))
        fd.seek(next_off)
    if sum(len(_encode_string(s)) for s in itos) != strings_len:
        raise ValueError("TXML string table size mismatch")
    fd.seek(strings_blob_offset + strings_len)
    out = io.StringIO()
    _write_xml_node(fd, itos, 0, out)
    return out.getvalue()


def is_value_node(node: ET.Element) -> bool:
    return len(node) == 0 and "type" in node.attrib and node.attrib["type"] in TXML_TYPE_DESCS_FROM_STR


def _traverse_xml_for_strings(node: ET.Element, strings: List[str], seen: set) -> None:
    for child in node:
        _traverse_xml_for_strings(child, strings, seen)
    tag = node.tag
    if tag not in seen:
        strings.append(tag)
        seen.add(tag)
    if is_value_node(node):
        if node.attrib["type"] == "string":
            val = node.attrib["value"]
            if val not in seen:
                strings.append(val)
                seen.add(val)
    else:
        for attr, val in node.items():
            if attr not in seen:
                strings.append(attr)
                seen.add(attr)
            if val not in seen:
                strings.append(val)
                seen.add(val)


class _BinWriter:
    def __init__(self) -> None:
        self.buf = io.BytesIO()

    def write(self, data: bytes) -> None:
        self.buf.write(data)

    def pack(self, fmt: str, *data) -> None:
        self.buf.write(struct.pack("<" + fmt, *data))


def _write_txml_value_node(node: ET.Element, stoi: Dict[str, int], w: _BinWriter) -> None:
    w.pack("I", stoi[node.tag])
    type_str = node.attrib["type"]
    type_i, attrs = TXML_TYPE_DESCS_FROM_STR[type_str]
    w.pack("I", type_i)
    if type_str == "string":
        w.pack("I", stoi[node.attrib["value"]])
    elif type_str == "byte_array":
        hex_parts = [p for p in node.attrib["value"].split(" ") if p]
        data = [int(x, 16) for x in hex_parts]
        w.pack("I", len(data))
        if data:
            w.pack("B" * len(data), *data)
    else:
        for pack_fmt, attr_name in attrs:
            val_str = node.attrib[attr_name]
            if pack_fmt == "B":
                val = int(val_str, 16)
            elif pack_fmt in ["I", "Q", "H"]:
                val = int(val_str)
            elif pack_fmt == "f":
                val = float(val_str)
            elif pack_fmt == "?":
                val = val_str not in ("0", "false", "False", "")
            else:
                raise ValueError(f"Unknown pack format {pack_fmt}")
            w.pack(pack_fmt, val)


def _write_txml_node(node: ET.Element, stoi: Dict[str, int], w: _BinWriter) -> None:
    w.pack("I", stoi[node.tag])
    w.pack("I", len(node.attrib))
    for attr, val in node.attrib.items():
        w.pack("I", stoi[attr])
        w.pack("I", stoi[val])
    value_nodes = []
    sub_nodes = []
    for child in node:
        if is_value_node(child):
            value_nodes.append(child)
        else:
            sub_nodes.append(child)
    w.pack("I", len(value_nodes))
    for vn in value_nodes:
        _write_txml_value_node(vn, stoi, w)
    w.pack("I", len(sub_nodes))
    for sn in sub_nodes:
        _write_txml_node(sn, stoi, w)


def xml_string_to_txml(xml_text: str) -> bytes:
    root = ET.fromstring(xml_text)
    return xml_element_to_txml(root)


def xml_element_to_txml(root: ET.Element) -> bytes:
    strings = [""]
    seen = {""}
    _traverse_xml_for_strings(root, strings, seen)
    stoi = {s: i for i, s in enumerate(strings)}
    encoded = [_encode_string(s) for s in strings]
    strings_blob = b"".join(encoded)
    w = _BinWriter()
    w.write(TXML_HEADER)
    w.write(TXML_HEADER_UNKNOWN)
    w.write(TXML_NULL_SPACER)
    w.pack("I", len(strings))
    w.pack("I", len(strings_blob))
    offset = 0
    for raw in encoded:
        w.pack("I", offset)
        w.pack("I", len(raw))
        offset += len(raw)
    w.write(strings_blob)
    _write_txml_node(root, stoi, w)
    return w.buf.getvalue()


def txml_file_to_xml(path: str) -> str:
    with open(path, "rb") as f:
        return txml_to_xml_string(f.read())


def xml_file_to_txml(path: str) -> bytes:
    tree = ET.parse(path)
    return xml_element_to_txml(tree.getroot())
