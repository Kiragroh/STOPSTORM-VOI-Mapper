"""Versioned catalogues; optional TG-263 import from the official worksheet."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import urllib.request

from .core import MASTERS

TG_URL = 'https://www.aapm.org/pubs/reports/rpt_263_supplemental/TG263_Nomenclature_Worksheet_20170815.xls'
TG_SHA256 = '5ff0b9e2ebf578793f6fa8f59c2357b3feb61fdc0f87171e9103a0495d93d150'
DEFAULT_TG = Path(os.environ.get('LOCALAPPDATA', Path.home() / '.cache')) / 'stopstorm-voi-mapper' / 'tg263.json'


def import_tg263(source=None, destination=DEFAULT_TG):
    """Explicit user command only; never called on page load."""
    import xlrd
    if source:
        data = Path(source).read_bytes()
    else:
        with urllib.request.urlopen(TG_URL, timeout=30) as response:
            if not response.url.startswith('https://www.aapm.org/'):
                raise ValueError('Unexpected TG-263 download location')
            data = response.read(8 * 1024 * 1024)
    digest = hashlib.sha256(data).hexdigest()
    if digest != TG_SHA256:
        raise ValueError('TG-263 worksheet checksum changed; inspect the source before importing.')
    sheet = xlrd.open_workbook(file_contents=data).sheet_by_name('TG263 v20170815')
    headers = sheet.row_values(0)
    fields = ['TG263-Primary Name', 'TG-263-Reverse Order Name', 'Description']
    indices = [headers.index(f) for f in fields]
    entries = []
    for row in range(1, sheet.nrows):
        name, reverse, description = [str(sheet.cell_value(row, i)).strip() for i in indices]
        if name:
            entries.append({'name': name, 'description': description, 'aliases': [reverse] if reverse else []})
    if len({e['name'] for e in entries}) != len(entries):
        raise ValueError('Duplicate primary names in source')
    result = {'id': 'tg263', 'version': sheet.name, 'source': TG_URL,
              'sha256': digest, 'attribution': 'American Association of Physicists in Medicine (AAPM), TG-263.',
              'entries': entries}
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result


def load_catalogues(path=DEFAULT_TG):
    result = {'stopstorm': {'id': 'stopstorm', 'version': 'STOPSTORM 40-VOI',
                           'entries': [{'name': n, 'description': '', 'aliases': []} for n in MASTERS]}}
    if Path(path).is_file():
        tg = json.loads(Path(path).read_text(encoding='utf-8'))
        if tg.get('sha256') != TG_SHA256 or not tg.get('entries'):
            raise ValueError('Unrecognised TG-263 catalogue; reimport the official worksheet.')
        result['tg263'] = tg
    return result


def main():
    parser = argparse.ArgumentParser(description='Import the pinned official AAPM TG-263 worksheet.')
    parser.add_argument('--source', type=Path, help='Previously downloaded official .xls worksheet')
    parser.add_argument('--output', type=Path, default=DEFAULT_TG)
    args = parser.parse_args()
    result = import_tg263(args.source, args.output)
    print(f"Imported {len(result['entries'])} names to {args.output}")


if __name__ == '__main__':
    main()
