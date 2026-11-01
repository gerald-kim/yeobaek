"""Structural and shaping checks for the Yeobaek pair (SIL OFL 1.1)."""
import argparse
import json
from pathlib import Path

from fontTools.ttLib import TTFont
from shaping import shape


def verify_pair(directory, libron_dir):
    directory, libron_dir = Path(directory), Path(libron_dir)
    fonts = {}
    checks = {}
    for style, weight, selection, mac_style in [('Regular', 400, 64, 0), ('Bold', 700, 32, 1)]:
        path = directory / f'Yeobaek-{style}.ttf'
        font = TTFont(path, checkChecksums=2)
        source_path = libron_dir / f'Libron-{style}.ttf'
        source = TTFont(source_path)
        fonts[style] = font
        assert font['name'].getName(1, 3, 1, 0x409).toUnicode() == 'Yeobaek'
        assert font['name'].getName(1, 3, 1, 0x412).toUnicode() == '여백'
        assert font['name'].getDebugName(2) == style
        assert font['name'].getDebugName(6) == f'Yeobaek-{style}'
        assert font['OS/2'].usWeightClass == weight
        assert font['OS/2'].fsSelection == selection
        assert font['head'].macStyle == mac_style
        cmap = font.getBestCmap()
        for cp in range(0xAC00, 0xD7A4):
            assert font['glyf'][cmap[cp]].numberOfContours > 0
        # The merger preserves Latin glyph order. Every point must be translated
        # down once, including components and unencoded ligatures/alternates.
        shift = round(-0.07 * source['head'].unitsPerEm)
        for gid, name in enumerate(source.getGlyphOrder()):
            dest_name = font.getGlyphOrder()[gid]
            old, ends, flags = source['glyf'][name].getCoordinates(source['glyf'])
            new, new_ends, new_flags = font['glyf'][dest_name].getCoordinates(font['glyf'])
            assert list(ends) == list(new_ends) and list(flags) == list(new_flags)
            assert len(old) == len(new)
            for (x, y), (xx, yy) in zip(old, new):
                assert abs(x - xx) <= 0.5 and abs(y + shift - yy) <= 0.5
            assert source['hmtx'][name] == font['hmtx'][dest_name]
        for sample in ['AVATAR To office affinity ffi fi fl 0123456789',
                       'café naïve Ångström a\u0301 e\u0323\u0301']:
            assert shape(source_path, sample) == shape(path, sample)
        for sample in ['한글 가나다 뚫 뺨 빽 뿜 똠 힣', '한글', '2026년 English와 한글']:
            assert all(item[0] != 0 for item in shape(path, sample))
        checks[style] = {'hangul_syllables': 11172, 'latin_geometry_and_shaping': 'passed',
                         'family_and_style': 'passed'}
    a, b = fonts['Regular'], fonts['Bold']
    assert set(a.getBestCmap()) == set(b.getBestCmap())
    for tag, attrs in [('hhea', ('ascent', 'descent', 'lineGap')),
                       ('OS/2', ('sTypoAscender', 'sTypoDescender', 'sTypoLineGap',
                                 'usWinAscent', 'usWinDescent'))]:
        for attr in attrs:
            assert getattr(a[tag], attr) == getattr(b[tag], attr)
    for cp in range(0xAC00, 0xD7A4):
        assert a['hmtx'][a.getBestCmap()[cp]][0] == b['hmtx'][b.getBestCmap()[cp]][0]
    checks['pair'] = {'line_metrics_and_hangul_advances': 'matched'}
    return checks


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('libron_dir', type=Path)
    args = parser.parse_args()
    print(json.dumps(verify_pair(args.directory, args.libron_dir), indent=2))
