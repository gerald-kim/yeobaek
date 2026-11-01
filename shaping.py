"""HarfBuzz binding adapted from Libron scripts/generate_specimens.py.

Copyright (c) 2026 Nico Verbruggen. SIL OFL 1.1; see LICENSE.
Source: aa1bf957f88629b1232bcdb2da02f199f1fb0a21.
Uses the HarfBuzz shared library already in the pinned build container.
"""
import ctypes as ct
from ctypes.util import find_library
from contextlib import ExitStack
from fontTools.ttLib import TTFont

class GlyphInfo(ct.Structure):
    _fields_ = [(name, ct.c_uint32) for name in
                ("codepoint", "mask", "cluster", "var1", "var2")]


class GlyphPosition(ct.Structure):
    _fields_ = [(name, ct.c_int32) for name in
                ("x_advance", "y_advance", "x_offset", "y_offset", "var")]


class Feature(ct.Structure):
    _fields_ = [(name, ct.c_uint32) for name in ("tag", "value", "start", "end")]


def harfbuzz():
    library = find_library("harfbuzz")
    if not library:
        raise RuntimeError("HarfBuzz is required. Run this script in fntbld-oci.")
    hb = ct.CDLL(library)
    pointer = ct.c_void_p
    signatures = {
        "blob_create_from_file_or_fail": (pointer, [ct.c_char_p]),
        "face_create": (pointer, [pointer, ct.c_uint]),
        "font_create": (pointer, [pointer]),
        "ot_font_set_funcs": (None, [pointer]),
        "font_set_scale": (None, [pointer, ct.c_int, ct.c_int]),
        "buffer_create": (pointer, []),
        "buffer_add_utf8": (None, [pointer, ct.c_char_p, ct.c_int, ct.c_uint, ct.c_int]),
        "buffer_guess_segment_properties": (None, [pointer]),
        "language_from_string": (pointer, [ct.c_char_p, ct.c_int]),
        "buffer_set_language": (None, [pointer, pointer]),
        "feature_from_string": (ct.c_int, [ct.c_char_p, ct.c_int, ct.POINTER(Feature)]),
        "shape": (None, [pointer, pointer, ct.POINTER(Feature), ct.c_uint]),
        "buffer_get_glyph_infos": (ct.POINTER(GlyphInfo), [pointer, ct.POINTER(ct.c_uint)]),
        "buffer_get_glyph_positions": (ct.POINTER(GlyphPosition), [pointer, ct.POINTER(ct.c_uint)]),
    }
    for resource in ("blob", "face", "font", "buffer"):
        signatures[f"{resource}_destroy"] = (None, [pointer])
    for name, (result, arguments) in signatures.items():
        function = getattr(hb, f"hb_{name}")
        function.restype = result
        function.argtypes = arguments
    return hb


class Font:
    def __init__(self, path, hb, resources):
        self.tt = resources.enter_context(TTFont(path))
        self.upm = self.tt["head"].unitsPerEm
        self.hb = hb
        blob = hb.hb_blob_create_from_file_or_fail(str(path).encode())
        if not blob:
            raise RuntimeError(f"Cannot load font: {path}")
        resources.callback(hb.hb_blob_destroy, blob)
        face = hb.hb_face_create(blob, 0)
        resources.callback(hb.hb_face_destroy, face)
        self.font = hb.hb_font_create(face)
        resources.callback(hb.hb_font_destroy, self.font)
        hb.hb_ot_font_set_funcs(self.font)
        hb.hb_font_set_scale(self.font, self.upm, self.upm)

    def shape(self, text, features=(), language="en"):
        hb = self.hb
        buffer = hb.hb_buffer_create()
        try:
            encoded = text.encode("utf-8")
            hb.hb_buffer_add_utf8(buffer, encoded, len(encoded), 0, len(encoded))
            hb.hb_buffer_set_language(buffer, hb.hb_language_from_string(language.encode(), -1))
            hb.hb_buffer_guess_segment_properties(buffer)
            settings = (Feature * len(features))()
            for i, setting in enumerate(features):
                if not hb.hb_feature_from_string(setting.encode(), -1, ct.byref(settings[i])):
                    raise ValueError(f"Invalid OpenType feature: {setting}")
            hb.hb_shape(self.font, buffer, settings, len(settings))
            count = ct.c_uint()
            infos = hb.hb_buffer_get_glyph_infos(buffer, ct.byref(count))
            positions = hb.hb_buffer_get_glyph_positions(buffer, ct.byref(count))
            glyphs = []
            for i in range(count.value):
                if infos[i].codepoint == 0:
                    raise ValueError(f"Missing glyph in {text!r}")
                p = positions[i]
                glyphs.append((infos[i].codepoint, p.x_advance, p.y_advance, p.x_offset, p.y_offset))
            return glyphs
        finally:
            hb.hb_buffer_destroy(buffer)


def shape(path, text):
    with ExitStack() as resources:
        return Font(path, harfbuzz(), resources).shape(text)
