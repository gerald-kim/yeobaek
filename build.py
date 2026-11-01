#!/usr/bin/env python3
"""Build Yeobaek Regular and Bold from pinned Libron/RIDIBatang inputs.

Derived from the Libron build experiment. Distributed under SIL OFL 1.1;
see LICENSE for the upstream copyright notices and license terms.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from fontTools import subset
from fontTools.merge import Merger
from fontTools.ttLib import TTFont
from fontTools.ttLib.scaleUpem import scale_upem

def name_yeobaek(font, style, copyright_text, suffix=''):
    """Name the two faces consistently, including Korean family records."""
    family = 'Yeobaek' + (' ' + suffix if suffix else '')
    korean_family = '여백' + (' ' + suffix if suffix else '')
    ps_name = family.replace(' ', '') + '-' + style
    font['name'].names = []
    names = {0: copyright_text, 1: family, 2: style,
             3: ps_name + '-0.004', 4: family + ' ' + style,
             5: 'Version 0.004', 6: ps_name,
             13: 'Licensed under the SIL Open Font License, Version 1.1.',
             14: 'https://openfontlicense.org', 16: family, 17: style}
    for name_id, value in names.items():
        font['name'].setName(value, name_id, 3, 1, 0x409)
    for name_id, value in {1: korean_family, 2: style,
                           4: korean_family + ' ' + style,
                           16: korean_family, 17: style}.items():
        font['name'].setName(value, name_id, 3, 1, 0x412)
    font['head'].fontRevision = 0.004
    return ps_name


def build_face(ridi_path, latin_path, out, style, latin_shift_em=-0.07,
               stroke_em=0.0, metrics_from=None):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    ridi_path = Path(ridi_path).resolve()
    latin_path = Path(latin_path).resolve()
    latin = TTFont(latin_path)
    expected_weight = 700 if style == 'Bold' else 400
    if latin['OS/2'].usWeightClass != expected_weight:
        raise ValueError('Latin source weight does not match requested style')
    latin_input = latin_path
    shift = round(latin_shift_em * latin['head'].unitsPerEm)
    if shift:
        from fontTools.ttLib.tables._g_l_y_f import Glyph
        from fontTools.ttLib.tables.ttProgram import Program
        # Resolve composites against the original table before replacing glyphs,
        # so accents and component transforms receive exactly one translation.
        translated = {}
        for name in latin.getGlyphOrder():
            coords, ends, flags = latin['glyf'][name].getCoordinates(latin['glyf'])
            glyph = Glyph()
            glyph.numberOfContours = len(ends)
            if ends:
                glyph.coordinates = coords.copy()
                glyph.coordinates.translate((0, shift))
                glyph.endPtsOfContours = list(ends)
                glyph.flags = flags.copy()
                glyph.program = Program()
                glyph.program.fromBytecode(b'\x00')
            translated[name] = glyph
        latin['glyf'].glyphs = translated
        latin_input = out / 'latin-shifted.ttf'
        latin.save(latin_input)
    ridi = TTFont(ridi_path)
    copyright_text = "\n".join(filter(None, [latin['name'].getDebugName(0), ridi['name'].getDebugName(0)]))
    original_ridi_cmap = set(ridi.getBestCmap())
    if stroke_em:
        import pathops
        from fontTools.fontBuilder import FontBuilder
        from fontTools.pens.cu2quPen import Cu2QuPen
        from fontTools.pens.ttGlyphPen import TTGlyphPen
        stroke = stroke_em * ridi['head'].unitsPerEm
        glyph_set = ridi.getGlyphSet()
        glyphs = {}
        for name in ridi.getGlyphOrder():
            original = pathops.Path()
            glyph_set[name].draw(original.getPen())
            border = pathops.Path(original)
            border.stroke(stroke, pathops.LineCap.BUTT_CAP,
                          pathops.LineJoin.ROUND_JOIN, 4)
            border.convertConicsToQuads(0.1)
            expanded = pathops.op(original, border, pathops.PathOp.UNION,
                                  clockwise=True)
            expanded.convertConicsToQuads(0.1)
            pen = TTGlyphPen(None)
            expanded.draw(Cu2QuPen(pen, max_err=0.5))
            glyphs[name] = pen.glyph()
        if 'CFF ' in ridi:
            del ridi['CFF ']
        ridi.sfntVersion = '\x00\x01\x00\x00'
        builder = FontBuilder(font=ridi)
        builder.isTTF = True
        builder.setupGlyf(glyphs)
        builder.setupMaxp()
        # Preserve advances, but keep side-bearing metadata aligned with bounds.
        for name, glyph in glyphs.items():
            advance, _ = ridi['hmtx'][name]
            ridi['hmtx'][name] = (advance, getattr(glyph, 'xMin', 0))
        ridi.save(out / 'ridi-emboldened.ttf')
    elif 'CFF ' in ridi:
        converted = out / 'ridi-converted.ttf'
        subprocess.run(['fontforge', '-lang', 'ff', '-c',
                        'Open($1); Generate($2)', str(ridi_path), str(converted)], check=True)
        ridi = TTFont(converted)
    scale_upem(ridi, latin['head'].unitsPerEm)
    latin_chars = set(latin.getBestCmap())
    ridi_chars = set(ridi.getBestCmap()) - latin_chars
    options = subset.Options()
    options.layout_features = ['*']
    sub = subset.Subsetter(options=options)
    sub.populate(unicodes=ridi_chars)
    sub.subset(ridi)
    # Horizontal reading prototype; the Latin source has no vertical tables.
    for tag in ('BASE', 'VORG', 'vhea', 'vmtx', 'DSIG'):
        if tag in ridi:
            del ridi[tag]
    # Share line metrics before merge, then enlarge clipping metrics if needed.
    for attr in ('ascent', 'descent', 'lineGap', 'caretSlopeRise', 'caretSlopeRun', 'caretOffset'):
        setattr(ridi['hhea'], attr, getattr(latin['hhea'], attr))
    ridi_subset = out / 'ridi-subset.ttf'
    ridi.save(ridi_subset)
    merged = Merger().merge([str(latin_input), str(ridi_subset)])
    ps_name = name_yeobaek(merged, style, copyright_text, '')
    merged['OS/2'].usWeightClass = expected_weight
    merged['OS/2'].fsSelection = 0x20 if style == 'Bold' else 0x40
    if style == 'Bold':
        merged['OS/2'].panose.bWeight = 8
    merged['OS/2'].fsType = 0
    merged['head'].macStyle = 1 if style == 'Bold' else 0
    for glyph_name in merged.getGlyphOrder():
        merged['glyf'][glyph_name].recalcBounds(merged['glyf'])
    ymax = max(getattr(g, 'yMax', 0) for g in merged['glyf'].glyphs.values())
    ymin = min(getattr(g, 'yMin', 0) for g in merged['glyf'].glyphs.values())
    merged['OS/2'].usWinAscent = max(merged['OS/2'].usWinAscent, ymax)
    merged['OS/2'].usWinDescent = max(merged['OS/2'].usWinDescent, -ymin)
    merged['hhea'].ascent = max(merged['hhea'].ascent, ymax)
    merged['hhea'].descent = min(merged['hhea'].descent, ymin)
    if metrics_from:
        reference = TTFont(metrics_from)
        if reference['head'].unitsPerEm != merged['head'].unitsPerEm:
            raise ValueError('Line-metric reference must have the same units/em')
        if reference['OS/2'].usWinAscent < ymax or reference['OS/2'].usWinDescent < -ymin:
            raise ValueError('Reference clipping metrics cannot contain the Bold outlines')
        for tag, attrs in [('hhea', ('ascent', 'descent', 'lineGap')),
                           ('OS/2', ('sTypoAscender', 'sTypoDescender', 'sTypoLineGap',
                                     'usWinAscent', 'usWinDescent'))]:
            for attr in attrs:
                setattr(merged[tag], attr, getattr(reference[tag], attr))
    target = out / (ps_name + '.ttf')
    merged.save(target)
    check = TTFont(target, checkChecksums=2)
    assert set(check.getBestCmap()) == latin_chars | original_ridi_cmap
    assert all(cp in check.getBestCmap() for cp in range(0xAC00, 0xD7A4))
    sources = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (latin_path, ridi_path)}
    report = {'sources_sha256': sources, 'latin_characters': len(latin_chars),
              'ridi_added_characters': len(ridi_chars), 'total_characters': len(check.getBestCmap()),
              'upem': check['head'].unitsPerEm, 'ridi_scale': 1.0, 'ridi_baseline_shift': 0,
              'latin_shift_units': shift, 'latin_shift_em': latin_shift_em,
              'style': style, 'ridi_stroke_em': stroke_em,
              'metrics_from': metrics_from,
              'output_sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
    return target, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ridi', required=True, type=Path)
    parser.add_argument('--libron-dir', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    manifest = json.loads((root / 'sources.json').read_text())
    inputs = {'RIDIBatang.otf': args.ridi,
              'Libron-Regular.ttf': args.libron_dir / 'Libron-Regular.ttf',
              'Libron-Bold.ttf': args.libron_dir / 'Libron-Bold.ttf'}
    for name, path in inputs.items():
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != manifest['sha256'][name]:
            parser.error(f'{name}: SHA-256 differs from sources.json; review the input before updating the manifest')
    args.output.mkdir(parents=True, exist_ok=False)
    reports = {}
    with tempfile.TemporaryDirectory(prefix='yeobaek-') as work:
        regular, report = build_face(args.ridi, inputs['Libron-Regular.ttf'],
                                     Path(work) / 'regular', 'Regular')
        reports['Regular'] = report
        bold, report = build_face(args.ridi, inputs['Libron-Bold.ttf'],
                                  Path(work) / 'bold', 'Bold', stroke_em=0.020,
                                  metrics_from=str(regular))
        reports['Bold'] = report
        for path in (regular, bold):
            shutil.copy2(path, args.output / path.name)
    for report in reports.values():
        report['sources_sha256'] = {Path(k).name: v for k, v in report['sources_sha256'].items()}
        if report['metrics_from']:
            report['metrics_from'] = Path(report['metrics_from']).name
    shutil.copy2(root / 'LICENSE', args.output / 'OFL.txt')
    shutil.copy2(root / 'sources.json', args.output / 'sources.json')
    shutil.copy2(root / 'specimen.html', args.output / 'specimen.html')
    (args.output / 'build-report.json').write_text(json.dumps(reports, indent=2) + '\n')
    from verify import verify_pair
    validation = verify_pair(args.output, args.libron_dir)
    (args.output / 'validation.json').write_text(json.dumps(validation, indent=2) + '\n')
    print(f'Built and verified: {args.output}')


if __name__ == '__main__':
    main()
