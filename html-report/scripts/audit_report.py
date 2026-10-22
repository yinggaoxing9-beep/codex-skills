#!/usr/bin/env python3
"""Static checks for an HTML report, plus opt-in horizontal bar geometry.

Standard library only. No browser execution, network requests, or HTML mutation.
Exit 1 on errors, 0 otherwise; warnings require human review.
"""
import argparse
from collections import Counter
from dataclasses import dataclass, field
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit


@dataclass
class Node:
    tag: str
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)
    content: list = field(default_factory=list)

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()

    def text(self):
        return ''.join(part if isinstance(part, str) else part.text() for part in self.content)


class Document(HTMLParser):
    VOID = set('area base br col embed hr img input link meta param source track wbr'.split())

    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.root = Node('document')
        self.stack = [self.root]
        self.feed(source)
        self.close()

    def handle_starttag(self, tag, attrs):
        node = Node(tag, dict(attrs))
        self.stack[-1].children.append(node)
        self.stack[-1].content.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        self.stack[-1].content.append(data)


def number(value):
    result = float(str(value).strip().replace(',', ''))
    if not math.isfinite(result):
        raise ValueError('number must be finite')
    return result


def audit(path, single_file=False):
    path = Path(path).resolve()
    source = path.read_text(encoding='utf-8-sig')
    doc = Document(source)
    nodes = list(doc.root.walk())
    errors, warnings = [], []

    def issue(level, code, message):
        (errors if level == 'error' else warnings).append({'code': code, 'message': message})

    id_nodes = [n for n in nodes if n.attrs.get('id')]
    ids = {n.attrs['id']: n for n in id_nodes}
    for key, count in Counter(n.attrs['id'] for n in id_nodes).items():
        if count > 1:
            issue('error', 'DUPLICATE_ID', f'{key}: {count} occurrences')
    if not any(n.tag == 'main' and n.text().strip() for n in nodes):
        issue('error', 'STATIC_MAIN', 'No nonempty main content in static HTML')
    if sum(n.tag == 'h1' for n in nodes) != 1:
        issue('warning', 'H1', 'Review document title hierarchy; expected one h1')
    if not any(n.tag == 'html' and n.attrs.get('lang') for n in nodes):
        issue('warning', 'LANG', 'Document language is missing')

    resources = []
    for n in nodes:
        href = n.attrs.get('href', '')
        if href.startswith('#') and len(href) > 1 and unquote(href[1:]) not in ids:
            issue('error', 'BROKEN_ANCHOR', href)
        if 'src' in n.attrs:
            resources.append(n.attrs['src'])
        if n.tag == 'link' and href:
            resources.append(href)
        if n.tag in {'image', 'use'}:
            resources.extend(n.attrs[k] for k in ('href', 'xlink:href') if n.attrs.get(k))
        if 'srcset' in n.attrs:
            issue('warning', 'SRCSET_MANUAL', 'Review srcset resources manually: ' + n.attrs['srcset'])
        if 'data-count' in n.attrs and not n.text().strip():
            issue('error', 'EMPTY_COUNTER', 'Animation counter has no final static number')
        if n.tag == 'details' and 'open' not in n.attrs:
            issue('warning', 'CLOSED_DETAILS', 'Review no-JS readability and printing of closed details')
        if n.tag in {'section', 'main'} and ('hidden' in n.attrs or re.search(r'display\s*:\s*none', n.attrs.get('style', ''), re.I)):
            issue('error', 'HIDDEN_CORE', 'Core section/main is statically hidden')
        if n.tag == 'img' and 'alt' not in n.attrs:
            issue('warning', 'IMAGE_ALT', 'Image has no alt attribute')

    css = '\n'.join(n.text() for n in nodes if n.tag == 'style')
    css += '\n' + '\n'.join(n.attrs.get('style', '') for n in nodes)
    resources.extend(re.findall(r'url\(\s*[\'"]?([^\)\'"\s]+)', css, re.I))
    resources.extend(re.findall(r'@import\s+[\'"]([^\'"]+)', css, re.I))
    for resource in sorted(set(resources)):
        parts = urlsplit(resource)
        if resource.startswith('#'):
            if unquote(resource[1:]) not in ids:
                issue('error', 'BROKEN_RESOURCE_ANCHOR', resource)
        elif parts.scheme == 'data':
            continue
        elif parts.netloc or parts.scheme in {'http', 'https'}:
            issue('error' if single_file else 'warning', 'REMOTE_RESOURCE', resource)
        elif parts.scheme or re.match(r'^[A-Za-z]:', resource) or resource.startswith(('/', '\\')):
            issue('error', 'MACHINE_RESOURCE', resource)
        else:
            if single_file:
                issue('error', 'NOT_SINGLE_FILE', resource)
            if not (path.parent / unquote(parts.path)).exists():
                issue('error', 'MISSING_RESOURCE', resource)
    if not re.search(r'@media\s+print', css, re.I):
        issue('warning', 'PRINT_CSS', 'No print media rules found')
    if 'prefers-reduced-motion' not in css:
        issue('warning', 'REDUCED_MOTION', 'No reduced-motion rules found')
    if ':focus' not in css:
        issue('warning', 'FOCUS', 'Review visible keyboard focus')
    scripts = '\n'.join(n.text() for n in nodes if n.tag == 'script')
    if re.search(r'\b(fetch|XMLHttpRequest|WebSocket|import)\s*\(', scripts):
        issue('warning', 'RUNTIME_REQUEST', 'Review runtime requests; core evidence must be static')

    charts = [n for n in nodes if n.attrs.get('data-chart') == 'bars']
    checked = 0
    for chart in charts:
        label = chart.attrs.get('id', chart.attrs.get('data-table', '(unnamed)'))
        try:
            if chart.tag != 'svg':
                raise ValueError('bar contract requires svg')
            table = ids[chart.attrs['data-table']]
            if table.tag != 'table':
                raise ValueError('data-table must point to table')
            values = {}
            for row in (n for n in table.walk() if n.tag == 'tr' and 'data-key' in n.attrs):
                key = row.attrs['data-key']
                cells = [n for n in row.walk() if 'data-value' in n.attrs]
                if key in values or len(cells) != 1:
                    raise ValueError('table keys must be unique with one data-value cell each')
                value = number(cells[0].text())
                if not math.isclose(value, number(cells[0].attrs['data-value']), abs_tol=1e-9):
                    issue('error', 'TABLE_VALUE', f'{label}/{key}: visible value differs from data-value')
                values[key] = value
            if not values:
                raise ValueError('numeric table is empty')
            low, high = number(chart.attrs['data-min']), number(chart.attrs['data-max'])
            left, width = number(chart.attrs['data-plot-x']), number(chart.attrs['data-plot-width'])
            scale = chart.attrs['data-scale']
            if high <= low or width <= 0 or scale not in {'linear', 'log'}:
                raise ValueError('invalid chart bounds, width or scale')
            if scale == 'linear' and low != 0:
                raise ValueError('linear bar contract requires a zero baseline')
            if scale == 'log' and low <= 0:
                raise ValueError('log scale minimum must be positive')

            def position(value):
                if value < low or value > high or (scale == 'log' and value <= 0):
                    raise ValueError(f'value/tick {value} outside valid scale')
                t = ((value - low) / (high - low) if scale == 'linear' else
                     (math.log(value) - math.log(low)) / (math.log(high) - math.log(low)))
                return left + width * t

            bars = [n for n in chart.walk() if 'data-bar' in n.attrs]
            labels = [n for n in chart.walk() if 'data-label' in n.attrs]
            for group, name in ((bars, 'bars'), (labels, 'labels')):
                keys = [n.attrs.get('data-key') for n in group]
                if set(keys) != set(values) or len(keys) != len(values):
                    raise ValueError(f'{name} must map to all table keys exactly once')
            for bar in bars:
                key = bar.attrs['data-key']
                expected = position(values[key]) - left
                if bar.tag != 'rect' or not math.isclose(number(bar.attrs['x']), left, abs_tol=.01) or not math.isclose(number(bar.attrs['width']), expected, abs_tol=.01):
                    issue('error', 'BAR_GEOMETRY', f'{label}/{key}: expected x={left:g}, width={expected:g}; got x={bar.attrs.get("x")}, width={bar.attrs.get("width")}')
                if any(k in bar.attrs for k in ('style', 'transform')):
                    issue('warning', 'BAR_OVERRIDE', f'{label}/{key}: review style/transform overrides manually')
            for text_node in labels:
                if text_node.tag != 'text' or not math.isclose(number(text_node.text()), values[text_node.attrs['data-key']], abs_tol=1e-9):
                    issue('error', 'BAR_LABEL', f'{label}: numeric label differs from table')
            ticks = [n for n in chart.walk() if 'data-tick' in n.attrs]
            if len(ticks) < 2:
                issue('warning', 'TICKS', f'{label}: review missing scale ticks')
            for tick in ticks:
                value = number(tick.attrs['data-tick'])
                expected_x = position(value)
                if not math.isclose(number(tick.attrs['x']), expected_x, abs_tol=.01) or not math.isclose(number(tick.text()), value, abs_tol=1e-9):
                    issue('error', 'TICK_GEOMETRY', f'{label}: tick {value:g} should be at x={expected_x:g} with matching label')
            checked += 1
        except (KeyError, ValueError, TypeError, OverflowError) as exc:
            issue('error', 'CHART_CONTRACT', f'{label}: {exc}')

    unknown_svg = sum(n.tag == 'svg' and n.attrs.get('data-chart') != 'bars' for n in nodes)
    canvas = sum(n.tag == 'canvas' for n in nodes)
    if unknown_svg:
        issue('warning', 'SVG_MANUAL', f'{unknown_svg} SVG(s) outside bar contract; geometry not audited')
    if canvas:
        issue('warning', 'CANVAS_MANUAL', f'{canvas} canvas element(s); check static equivalent and geometry manually')
    issue('warning', 'MANUAL_REVIEW', 'CSS graphics, CSS overrides, unsupported chart types, rendered no-JS readability, print pagination, evidence and accessibility require manual review')
    return {
        'file': str(path), 'passed_static_checks': not errors,
        'scope': 'Static HTML and opt-in horizontal SVG bars only; no browser, CSS cascade or source verification',
        'coverage': {'bar_contract_charts': len(charts), 'bar_charts_processed': checked,
                     'unrecognized_svg': unknown_svg, 'canvas': canvas, 'css_geometry': 'not-audited'},
        'errors': errors, 'warnings': warnings,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('html', type=Path)
    parser.add_argument('--single-file', action='store_true', help='Reject runtime external/local resources; citations remain allowed')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    try:
        report = audit(args.html, args.single_file)
    except (OSError, UnicodeError, ValueError) as exc:
        parser.exit(2, f'Cannot audit input: {exc}\n')
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print('Static checks: ' + ('PASS' if report['passed_static_checks'] else 'FAIL'))
        print(report['scope'])
        for kind in ('errors', 'warnings'):
            for entry in report[kind]:
                print(f'{kind}: {entry["code"]}: {entry["message"]}')
    raise SystemExit(0 if report['passed_static_checks'] else 1)


if __name__ == '__main__':
    main()
