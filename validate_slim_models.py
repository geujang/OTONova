"""Compare actual CPU predictions and forced boundaries against v27 originals."""
from pathlib import Path
import json
import argparse
import subprocess
import numpy as np

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'build/model-slim-validation'
OLD = ROOT / 'release/WFL-Oto-Windows-v27'
PYTHON = ROOT / '.wfl-venv/Scripts/python.exe'


def run(base, backend, folder, requests):
    python = base / 'runtime/python.exe' if (base / 'runtime/python.exe').exists() else PYTHON
    process = subprocess.run([str(python), '-B', '-I', str(backend), str(base / 'WFL'), str(folder)],
        input=''.join(json.dumps(x) + '\n' for x in [*requests, {'close': True}]),
        text=True, capture_output=True, timeout=300)
    rows = [json.loads(line) for line in process.stdout.splitlines() if line.startswith('{')]
    if process.returncode or len(rows) != len(requests) + 1 or any('error' in x for x in rows):
        raise RuntimeError(process.stdout + '\n' + process.stderr)
    return rows[1:]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate', type=Path, default=ROOT)
    candidate = parser.parse_args().candidate.resolve()
    backend = candidate / ('tools/wfl_backend.py' if (candidate / 'tools/wfl_backend.py').exists() else '_internal/tools/wfl_backend.py')
    cases = {'en': ('English', ROOT / 'tools/research/arpasing/smoke-en/001.wav'),
             'ja': ('Japanese', next((ROOT / 'Natural-A4').glob('_あ息*.wav'))),
             'ko': ('WFL/Archivoice/korean', ROOT / "KO CVVC OTOOTO/_a'a'i'a'u'a'e'a.wav")}
    report = {}
    for lang, (folder, wav) in cases.items():
        expected = json.loads((OUT / (lang + '-original.json')).read_text(encoding='utf-8'))
        actual, forced = run(candidate, backend, candidate / folder, [
            {'wav': str(wav), 'cache': str(OUT / (lang + '-compact.npz'))},
            {'wav': str(wav), 'phones': [x[2] for x in expected['intervals']]}])
        assert actual == expected, (lang, 'decoded boundaries differ', actual, expected)
        with np.load(OUT / (lang + '-original.npz')) as original, np.load(OUT / (lang + '-compact.npz')) as compact:
            for field in ('logits', 'offsets', 'duration'):
                assert np.array_equal(original[field], compact[field]), (lang, field)
        original_forced = run(OLD, OLD / '_internal/tools/wfl_backend.py', OLD / folder,
                             [{'wav': str(wav), 'phones': [x[2] for x in expected['intervals']]}])[0]
        assert forced == original_forced, (lang, 'forced boundaries differ')
        report[lang] = {'logits_exact': True, 'offsets_exact': True,
                        'decoded_boundaries_exact': True, 'forced_boundaries_exact': True,
                        'wave': str(wav)}
        print(lang, 'all inference values and boundaries EXACT', flush=True)
    # Exercise all three language heads in one process, including shared encoder reuse.
    hybrid = []
    for base, backend in ((OLD, OLD / '_internal/tools/wfl_backend.py'),
                          (candidate, backend)):
        routes = {p: {'path': str(base / folder), 'phone': phone, 'language': language, 'fallback': fallback}
                  for p, folder, phone, language, fallback in (
                      ('dh', 'English', 'dh', 'en', 'd'), ('ts', 'Japanese', 'ts', 'ja', 'ch'),
                      ('er', 'English', 'r', 'en', 'L'), ('@r', 'English', 'r', 'en', 'L'))}
        hybrid.append(run(base, backend, base / 'WFL/Archivoice/korean', [{
            'wav': str(cases['ko'][1]), 'phones': ['SP', 'dh', 'a', 'ts', 'i', 'er', '@r', 'SP'],
            'aux_routes': routes}])[0])
    assert hybrid[0] == hybrid[1], 'hybrid boundaries differ'
    assert not hybrid[1]['alignment_warnings'], hybrid[1]
    report['hybrid'] = {'boundaries_exact': True, 'auxiliary_models_used': hybrid[1]['alignment_sources']}
    report['candidate'] = str(candidate)
    (OUT / 'inference-comparison.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
