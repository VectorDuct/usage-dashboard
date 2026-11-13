"""Create a deterministic source archive from a narrow publishing allowlist."""
import argparse
import hashlib
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = ['README.md', 'README.zh-CN.md', 'LICENSE', 'CONTRIBUTING.md', 'CHANGELOG.md',
         'pyproject.toml', 'Dockerfile', 'compose.yaml', '.gitignore', '.dockerignore']
PATTERNS = ['usage_dashboard/*.py', 'usage_dashboard/static/*.html',
            'usage_dashboard/static/*.css', 'usage_dashboard/static/*.js',
            'examples/*.json', 'docs/*.md', 'docs/demo-*.png',
            'tests/test_*.py', 'tests/browser.mjs', '.github/workflows/*.yml', 'tools/release.py']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist' / 'usage-dashboard-0.1.0.zip')
    args = parser.parse_args()
    files = {ROOT / name for name in FILES}
    for pattern in PATTERNS:
        files.update(ROOT.glob(pattern))
    payloads = {}
    for path in sorted(files):
        if not path.is_file() or path.is_symlink():
            raise ValueError('Missing file or symlink in publish list')
        if path.resolve().is_relative_to(ROOT) is False:
            raise ValueError('Publish path escapes project')
        payloads[str(path.relative_to(ROOT))] = path.read_bytes()
    manifest = ''.join(hashlib.sha256(data).hexdigest() + '  ' + name + '\n' for name, data in payloads.items())
    payloads['MANIFEST.sha256'] = manifest.encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in payloads.items():
            info = zipfile.ZipInfo('usage-dashboard/' + name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    print(f'{args.output.name}: {len(payloads)} files; sha256={hashlib.sha256(args.output.read_bytes()).hexdigest()}')


if __name__ == '__main__':
    main()
