#!/usr/bin/env python3
"""Render a self-contained Walden specimen from the actual TTF outlines.

SIL OFL 1.1; see LICENSE. English quotations are from Henry David Thoreau's
public-domain Walden. Korean translations were prepared for this specimen.
Source: https://www.gutenberg.org/files/205/205-h/205-h.htm
"""
import argparse
from contextlib import ExitStack
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from shaping import Font, harfbuzz

WIDTH, HEIGHT = 1200, 1360
INK, MUTED, ACCENT = '#292b27', '#6c7066', '#65745c'


def render(font_dir):
    definitions, elements = {}, []
    with ExitStack() as resources:
        fonts = {s: Font(font_dir / f'Yeobaek-{s}.ttf', harfbuzz(), resources)
                 for s in ('Regular', 'Bold')}
        glyphsets = {s: f.tt.getGlyphSet() for s, f in fonts.items()}

        def text(value, x, y, size, style='Regular', color=INK):
            font = fonts[style]
            scale = size / font.upm
            elements.append(f'<g fill="{color}" aria-label={quoteattr(value)}>')
            elements.append(f'<title>{escape(value)}</title>')
            for gid, advance, vertical, dx, dy in font.shape(value):
                name = font.tt.getGlyphName(gid)
                key = (style, gid)
                if key not in definitions:
                    glyph = glyphsets[style][name]
                    pen = SVGPathPen(glyphsets[style])
                    glyph.draw(pen)
                    bounds = BoundsPen(glyphsets[style])
                    glyph.draw(bounds)
                    definitions[key] = (f'g{len(definitions)}', pen.getCommands(), bounds.bounds)
                identifier, path, bounds = definitions[key]
                gx, gy = x + dx * scale, y - dy * scale
                if bounds:
                    left, bottom, right, top = bounds
                    if not (60 <= gx + left * scale and gx + right * scale <= WIDTH - 60
                            and 20 <= gy - top * scale and gy - bottom * scale <= HEIGHT - 20):
                        raise ValueError(f'Text outside specimen margins: {value}')
                if path:
                    elements.append(f'<use xlink:href="#{identifier}" transform="translate({gx:.3f} {gy:.3f}) scale({scale:.6f} {-scale:.6f})"/>')
                x += advance * scale
                y -= vertical * scale
            elements.append('</g>')

        def rule(y):
            elements.append(f'<path d="M76 {y}H1124" stroke="#d9dccf"/>')

        text('여백 · Yeobaek', 76, 133, 68)
        text('한글과 영어 사이, 편안하게 읽는 글자', 79, 187, 25, color=MUTED)
        text('Regular / Bold', 79, 225, 20, color=ACCENT)
        rule(260)

        text('01   여백 / Sounds', 76, 310, 19, color=ACCENT)
        text('I love a broad margin to my life.', 76, 379, 44)
        text('나는 삶에 넉넉한 여백을 두는 것을 좋아한다.', 76, 434, 29)

        text('02   시간 / Where I Lived, and What I Lived For', 76, 522, 19, color=ACCENT)
        text('Time is but the stream I go a-fishing in.', 76, 582, 35)
        text('시간은 내가 낚시하러 가는 시냇물일 뿐이다.', 76, 634, 29)

        text('03   세 개의 의자 / Visitors', 76, 722, 19, color=ACCENT)
        text('I had three chairs in my house; one for solitude,', 76, 779, 31)
        text('two for friendship, three for society.', 76, 824, 31)
        text('내 집에는 의자가 셋 있었다. 하나는 고독을 위해,', 76, 879, 28)
        text('둘은 우정을 위해, 셋은 사교를 위해.', 76, 921, 28)
        rule(963)

        text('한영·숫자 조판 예문 / Regular', 76, 1009, 19, color=ACCENT)
        mixed = '의자 1개는 solitude, 2개는 friendship, 3개는 society.'
        text(mixed, 76, 1058, 27)
        text('같은 문장 / Bold', 76, 1110, 19, color=ACCENT)
        text(mixed, 76, 1159, 27, style='Bold')
        text('0123456789   1,234.56   (1 / 2 / 3)', 76, 1218, 27)
        rule(1260)
        text('Henry David Thoreau, Walden · 영문 원문 발췌 / 한국어는 견본용 직접 번역',
             76, 1307, 16, color=MUTED)

    defs = ''.join(f'<path id="{identifier}" d="{path}"/>'
                   for identifier, path, _ in definitions.values() if path)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" '
            'aria-labelledby="title description">\n'
            '<title id="title">여백 Yeobaek — 월든으로 보는 Regular와 Bold</title>\n'
            '<desc id="description">월든의 여백, 시간, 세 개의 의자 대목을 영어와 한국어로 보여주고, '
            '의자 1개는 solitude, 2개는 friendship, 3개는 society라는 조판 예문을 두 굵기로 비교합니다.</desc>\n'
            f'<rect width="{WIDTH}" height="{HEIGHT}" fill="#f8f7f1"/>\n'
            f'<defs>{defs}</defs>\n' + '\n'.join(elements) + '\n</svg>\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('font_dir', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    svg = render(args.font_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as output:
        output.write(svg)
    print(f'Wrote {args.output} ({len(svg.encode()):,} bytes)')
