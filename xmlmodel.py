#!/usr/bin/env python3
"""Helpers for browsing and mutating TXML-as-XML trees."""

from __future__ import annotations

import copy
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

from catalog import identity_fields
from txml import TXML_TYPE_DESCS_FROM_STR, is_value_node


def parse_xml_file(path: str) -> ET.ElementTree:
    return ET.parse(path)


def write_xml_file(tree: ET.ElementTree, path: str) -> None:
    root = tree.getroot()
    text = _serialize(root, 0)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
        if not text.endswith("\n"):
            f.write("\n")


def _serialize(node: ET.Element, level: int) -> str:
    indent = "  " * level
    if is_value_node(node):
        attrs = " ".join(f"{k}='{_esc(v)}'" for k, v in node.attrib.items())
        return f"{indent}<{node.tag} {attrs}/>\n"
    attr_s = "".join(f" {k}='{_esc(v)}'" for k, v in node.attrib.items())
    children = list(node)
    if not children:
        return f"{indent}<{node.tag}{attr_s}>\n{indent}</{node.tag}>\n"
    parts = [f"{indent}<{node.tag}{attr_s}>\n"]
    for child in children:
        parts.append(_serialize(child, level + 1))
    parts.append(f"{indent}</{node.tag}>\n")
    return "".join(parts)


def _esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("'", "&apos;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def node_label(node: ET.Element, localization: Optional[Dict[str, str]] = None) -> str:
    if is_value_node(node):
        t = node.attrib.get("type", "")
        if t in ("string", "integer", "float", "bool", "long", "short"):
            return f"{node.tag} = {node.attrib.get('value', '')}"
        extra = " ".join(f"{k}={v}" for k, v in node.attrib.items() if k != "type")
        return f"{node.tag} ({t}) {extra}".strip()
    ident = record_identity(node)
    n = len(node)
    if ident:
        label = f"{node.tag}: {ident}"
        if localization:
            from project import localization_lookup
            friendly = localization_lookup(localization, ident)
            if friendly and friendly != ident:
                label += f"  —  {friendly}"
        label += f"  [{n} fields]"
        return label
    if n:
        return f"{node.tag}  [{n} children]"
    return node.tag


def record_identity(node: ET.Element) -> str:
    wanted = set(identity_fields())
    for child in node:
        if child.tag in wanted and child.attrib.get("value"):
            return child.attrib["value"]
        if child.tag in wanted and (child.text or "").strip():
            return child.text.strip()
    for key in ("name", "id", "typeName"):
        if node.attrib.get(key):
            return node.attrib[key]
    return ""


def matches_filter(node: ET.Element, needle: str) -> bool:
    if not needle:
        return True
    n = needle.lower()
    if n in node.tag.lower():
        return True
    if n in record_identity(node).lower():
        return True
    for k, v in node.attrib.items():
        if n in k.lower() or n in v.lower():
            return True
    for child in node:
        if is_value_node(child):
            blob = " ".join(child.attrib.values()).lower()
            if n in child.tag.lower() or n in blob:
                return True
    return False


def duplicate_node(parent: ET.Element, child: ET.Element) -> ET.Element:
    clone = copy.deepcopy(child)
    ident_tags = set(identity_fields())
    for sub in clone:
        if sub.tag in ident_tags and "value" in sub.attrib:
            sub.attrib["value"] = sub.attrib["value"] + "_copy"
            break
    idx = list(parent).index(child)
    parent.insert(idx + 1, clone)
    return clone


def delete_node(parent: ET.Element, child: ET.Element) -> None:
    parent.remove(child)


def add_value_child(parent: ET.Element, tag: str, type_str: str = "string", value: str = "") -> ET.Element:
    el = ET.SubElement(parent, tag)
    el.set("type", type_str)
    if type_str in ("2d_point_i", "2d_point_f"):
        el.set("x", "0")
        el.set("y", "0")
    elif type_str == "3d_point_f":
        el.set("x", "0")
        el.set("y", "0")
        el.set("z", "0")
    elif type_str == "color":
        el.set("r", "00")
        el.set("g", "00")
        el.set("b", "00")
        el.set("a", "FF")
    elif type_str == "size":
        el.set("width", "0")
        el.set("height", "0")
    elif type_str == "rectangle":
        el.set("x", "0")
        el.set("y", "0")
        el.set("width", "0")
        el.set("height", "0")
    elif type_str == "byte_array":
        el.set("value", "")
    else:
        el.set("value", value)
    return el


def add_container_child(parent: ET.Element, tag: str) -> ET.Element:
    return ET.SubElement(parent, tag)


def value_fields(node: ET.Element) -> List[Tuple[str, str]]:
    if not is_value_node(node):
        return [(k, v) for k, v in node.attrib.items()]
    return [(k, v) for k, v in node.attrib.items()]


KNOWN_TYPES = list(TXML_TYPE_DESCS_FROM_STR.keys())


def find_list_containers(root: ET.Element) -> List[ET.Element]:
    """Containers whose children look like repeated records."""
    found: List[ET.Element] = []

    def walk(node: ET.Element) -> None:
        children = list(node)
        if len(children) >= 2:
            tags = {c.tag for c in children}
            if len(tags) == 1 and not is_value_node(children[0]):
                found.append(node)
                return
        for child in children:
            if not is_value_node(child):
                walk(child)

    walk(root)
    return found


def iter_identity_values(node: ET.Element):
    """Yield (value, tag) for every identity-looking field under this record."""
    wanted = set(identity_fields())
    for child in node:
        if child.tag in wanted and child.attrib.get("value"):
            yield child.attrib["value"], child.tag
    for key in ("name", "id", "typeName"):
        if node.attrib.get(key):
            yield node.attrib[key], key


def build_definition_index(root: ET.Element) -> Dict[str, ET.Element]:
    """Map every identity value in the tree to the record node that declares it."""
    index: Dict[str, ET.Element] = {}

    def walk(node: ET.Element) -> None:
        if not is_value_node(node):
            for val, _tag in iter_identity_values(node):
                if val and val not in index:
                    index[val] = node
        for child in node:
            walk(child)

    walk(root)
    return index