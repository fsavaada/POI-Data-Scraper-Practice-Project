"""Build a clean source+data archive from an explicit allowlist, without Git."""
import csv
import hashlib
import json
import zipfile
from pathlib import Path
from check_repository import check

ROOT = Path(__file__).resolve().parents[1]
DATA_FILES = [
    'Datasets/ctrip_province_top20.csv',
    'Datasets/ctrip_province_top350.csv',
    'Datasets/dianping_guangzhou_10_shops.csv',
    'Datasets/dianping_national/restaurants.csv',
    'Datasets/dianping_national/restaurants.json',
    'Datasets/dianping_national/city_coverage.csv',
    'Datasets/dianping_national/quality_report.json',
    'Datasets/dianping_national/administrative_divisions.json',
    'Datasets/dianping_national/city_directory.json',
    'Datasets/dianping_national/district_evidence.json',
]
STATIC_FILES = ['README.md', 'THIRD_PARTY_NOTICES.md', 'requirements.txt', 'pyproject.toml',
                '.gitignore', '.gitattributes', '.github/workflows/tests.yml',
                'Datasets/README.md', 'Datasets/dianping_national/README.md']


def describe(path):
    body = path.read_bytes()
    record = {'path': path.relative_to(ROOT).as_posix(), 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}
    if path.suffix == '.csv':
        with path.open(encoding='utf-8-sig', newline='') as file:
            reader = csv.reader(file)
            record['columns'] = next(reader)
            record['rows'] = sum(1 for _ in reader)
    return record


def main():
    check()
    data_manifest = {'description': 'Unmodified collected result snapshots and public reference metadata.',
                     'files': [describe(ROOT / name) for name in DATA_FILES]}
    (ROOT / 'Datasets/manifest.json').write_text(json.dumps(data_manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    files = [ROOT / name for name in STATIC_FILES + DATA_FILES + ['Datasets/manifest.json']]
    for folder in ('Ctrip_Spider', 'Dianping_Spider', 'tests', 'scripts'):
        files.extend((ROOT / folder).glob('*.py'))
    files.extend((ROOT / 'docs').glob('*.md'))
    files = sorted(set(files))
    forbidden = {'.git', '.venv', 'node_modules', '__pycache__', '_cleanup_archive', 'boards', 'shops', 'child_boards'}
    for path in files:
        if not path.is_file() or not path.resolve().is_relative_to(ROOT) or forbidden.intersection(path.relative_to(ROOT).parts):
            raise ValueError('Invalid release path: ' + path.name)
        if path.stat().st_size >= 100 * 1024 * 1024:
            raise ValueError('Single release file exceeds 100 MiB: ' + path.name)
    release_manifest = {'files': [describe(path) for path in files], 'checks': check()}
    output = ROOT / 'dist/lifelens-crawlers-source-data.zip'
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            archive.write(path, path.relative_to(ROOT).as_posix())
        archive.writestr('RELEASE_MANIFEST.json', json.dumps(release_manifest, ensure_ascii=False, indent=2) + '\n')
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise ValueError('ZIP CRC validation failed')
        for record in release_manifest['files']:
            if hashlib.sha256(archive.read(record['path'])).hexdigest() != record['sha256']:
                raise ValueError('ZIP content hash mismatch: ' + record['path'])
    print(json.dumps({'archive': str(output), 'files': len(files) + 1, 'bytes': output.stat().st_size,
                      'checks': release_manifest['checks']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
