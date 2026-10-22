"""Losslessly split inference heads and their identical encoder after a Git backup."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import torch

ROOT = Path(__file__).resolve().parent
FORMAT = 'wfl-shared-encoder-v1'
MODELS = ('English', 'Japanese', 'WFL/Archivoice/korean')


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    subprocess.run(['git', '-c', f'safe.directory={ROOT.as_posix()}',
                    'rev-parse', '--verify', 'refs/tags/before-model-slim-v28'],
                   cwd=ROOT, check=True, capture_output=True)
    shared_path = ROOT / 'WFL/encoder/encoder.pt'
    if shared_path.exists():
        raise RuntimeError('Already converted; restore originals before converting again.')
    originals = {}
    shared = None
    report = {'format': FORMAT, 'backup_tag': 'before-model-slim-v28', 'models': {}}
    for name in MODELS:
        path = ROOT / name / 'last.ckpt'
        data = torch.load(path, map_location='cpu', weights_only=False)
        state = {k.removeprefix('model.'): v for k, v in data['state_dict'].items()}
        encoder = {k.removeprefix('encoder.'): v for k, v in state.items() if k.startswith('encoder.')}
        if shared is None:
            shared = {k: v.clone() for k, v in encoder.items()}
        elif shared.keys() != encoder.keys() or any(
                shared[k].dtype != v.dtype or shared[k].shape != v.shape or
                not torch.equal(shared[k], v) for k, v in encoder.items()):
            raise RuntimeError(f'{name}: encoders differ; cannot share losslessly')
        originals[name] = state
        report['models'][name] = {'original_bytes': path.stat().st_size,
                                 'original_sha256': digest(path), 'tensors': len(state)}
    torch.save({'format': FORMAT, 'state_dict': shared}, shared_path)
    shared_sha = digest(shared_path)
    saved_shared = torch.load(shared_path, map_location='cpu', weights_only=True)['state_dict']
    pending = []
    for name, state in originals.items():
        path = ROOT / name / 'last.ckpt'
        temporary = path.with_suffix('.slim.tmp')
        head = {k: v.clone() for k, v in state.items() if not k.startswith('encoder.')}
        torch.save({'format': FORMAT, 'state_dict': head,
                    'encoder_ref': Path(os.path.relpath(shared_path, path.parent)).as_posix(),
                    'encoder_sha256': shared_sha}, temporary)
        reloaded = torch.load(temporary, map_location='cpu', weights_only=True)['state_dict']
        restored = dict(reloaded, **{'encoder.' + k: v for k, v in saved_shared.items()})
        assert restored.keys() == state.keys()
        for key, value in state.items():
            assert restored[key].dtype == value.dtype and restored[key].shape == value.shape
            assert torch.equal(restored[key], value), (name, key)
        report['models'][name]['compact_bytes'] = temporary.stat().st_size
        report['models'][name]['all_tensors_exact'] = True
        pending.append((temporary, path))
    # No original is overwritten until every reconstructed state passes equality.
    del originals, state, data
    import gc
    gc.collect()
    for temporary, path in pending:
        temporary.replace(path)
    unused = ROOT / 'WFL/encoder/model.safetensors'
    assert unused.resolve().parent == shared_path.resolve().parent
    report['removed_base_model_bytes'] = unused.stat().st_size
    unused.unlink()
    report['shared_encoder_bytes'] = shared_path.stat().st_size
    report['shared_encoder_sha256'] = shared_sha
    report['original_total_bytes'] = sum(x['original_bytes'] for x in report['models'].values()) + report['removed_base_model_bytes']
    report['compact_total_bytes'] = sum(x['compact_bytes'] for x in report['models'].values()) + report['shared_encoder_bytes']
    (ROOT / 'model-slim-validation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
