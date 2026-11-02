"""Build an explicit static preview from the same frontend as the local app."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ('index.html', 'app.js', 'style.css')
OUTPUTS = set(ASSETS) | {'preview-config.js', 'version.json', '.nojekyll'}


def build_preview(root: Path, output: Path, commit: str) -> dict:
    output = Path(output)
    if output.is_symlink() or (output.exists() and not output.is_dir()):
        raise ValueError('Preview output must be a regular directory.')
    if output.exists() and any(path.name not in OUTPUTS or not path.is_file() or path.is_symlink() for path in output.iterdir()):
        raise ValueError('Preview output contains unexpected files; choose an empty directory.')
    source = root / 'static'
    for name in ASSETS:
        if not (source / name).is_file() or (source / name).is_symlink():
            raise ValueError(f'Missing or unsafe public asset: {name}')
    html = (source / 'index.html').read_text(encoding='utf8')
    entry = '<script src="./app.js"></script>'
    if html.count(entry) != 1:
        raise ValueError('Expected exactly one frontend entry script.')
    html = html.replace(entry, '<script src="./preview-config.js"></script>' + entry)
    if 'href="/style.css"' in html or 'src="/app.js"' in html:
        raise ValueError('Public assets must use relative URLs for repository subpaths.')
    output.mkdir(parents=True, exist_ok=True)
    for name in ASSETS[1:]:
        shutil.copyfile(source / name, output / name)
    (output / 'index.html').write_text(html, encoding='utf8')
    (output / 'preview-config.js').write_text('window.LINJING_PREVIEW_MODE = true;\n', encoding='utf8')
    version = {'mode':'frontend-preview', 'commit':commit, 'built_at':datetime.now(timezone.utc).isoformat()}
    (output / 'version.json').write_text(json.dumps(version, ensure_ascii=False, indent=2), encoding='utf8')
    (output / '.nojekyll').write_text('', encoding='utf8')
    return version


def main():
    commit = os.environ.get('GITHUB_SHA') or subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip()
    version = build_preview(ROOT, ROOT / 'web-preview', commit)
    print(json.dumps({'output':'web-preview', **version}, ensure_ascii=False))


if __name__ == '__main__':
    main()
