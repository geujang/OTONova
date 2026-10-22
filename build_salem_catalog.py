"""Read published Salem S-CVVC lists; distribute fingerprints, not source lists."""
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urljoin
import concurrent.futures
import gzip
import hashlib
import html
import json
import re

ROOT = Path(__file__).resolve().parent
BASE = 'https://utau.felinewasteland.com'


def canonical(text):
    return text.strip().lstrip('_+')


def main():
    research = ROOT / 'tools/research/salem'
    research.mkdir(parents=True, exist_ok=True)
    pages = {}
    for name in ('lite', 'full_ga'):
        pages[name] = urlopen(BASE + '/en/' + name, timeout=40).read().decode('utf-8')
        (research / (name + '.html')).write_text(pages[name], encoding='utf-8')
    urls = sorted({urljoin(BASE, path) for page in pages.values()
                   for path in re.findall(r'<script src="(/en/reclist/[^"]+)"', page)})
    def fetch(url):
        text = urlopen(url, timeout=40).read().decode('utf-8')
        (research / url.rsplit('/', 1)[-1]).write_text(text, encoding='utf-8')
        return url, text
    profiles = {}
    downloads = {variable: filename for page in pages.values() for variable, filename in
                 re.findall(r"makeTextFile\((\w+), 'text/plain', '([^']+\.txt)'", page)}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        for url, text in executor.map(fetch, urls):
            for variable, literal in re.findall(r'(\w+)\s*=\s*`([\s\S]*?)`\s*;', text):
                if variable not in downloads:
                    continue
                if '${' in literal:
                    raise ValueError('Unexpected executable template expression')
                lines = [html.unescape(line).strip() for line in re.sub(r'<br\s*/?>', '\n', literal).splitlines()]
                lines = list(dict.fromkeys(line for line in lines if line))
                assert lines and not any('<' in line or '>' in line for line in lines)
                fingerprints = sorted({hashlib.sha256(canonical(line).encode()).hexdigest()[:24] for line in lines})
                edition, beats, section = variable.split('_', 2)
                profiles[variable] = dict(edition=edition, beats=int(beats), section=section,
                    download=downloads[variable], source=url, lines=len(lines), fingerprints=fingerprints)
    assert len(profiles) == 28, len(profiles)
    data = dict(schema=1, family='Salem S-CVVC', overview=BASE+'/en/overview', profiles=profiles)
    output = ROOT / 'assets/salem-cvvc-catalog.json.gz'
    output.write_bytes(gzip.compress(json.dumps(data, separators=(',', ':')).encode(), mtime=0))
    print('Profiles:', len(profiles), 'strings:', sum(p['lines'] for p in profiles.values()), 'bytes:', output.stat().st_size)


if __name__ == '__main__':
    main()
