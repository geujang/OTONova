"""Package an existing, unchanged app into a verified drag-to-install DMG."""
from pathlib import Path
import argparse
import hashlib
import plistlib
import subprocess
import sys
import tempfile


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def package(app, output):
    if sys.platform != 'darwin':
        raise RuntimeError('DMG creation requires macOS and hdiutil.')
    app, output = Path(app).resolve(), Path(output).resolve()
    if app.name != 'OTONova.app' or not (app/'Contents/MacOS/OTONova').is_file():
        raise ValueError('Expected an existing OTONova.app bundle.')
    if output.exists():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    run = lambda *args: subprocess.run(args, check=True)
    with tempfile.TemporaryDirectory(prefix='otonova-dmg-') as directory:
        root = Path(directory)
        staging = root/'contents'
        staging.mkdir()
        run('ditto', str(app), str(staging/app.name))
        (staging/'Applications').symlink_to('/Applications', target_is_directory=True)
        run('hdiutil', 'create', '-volname', 'OTONova', '-srcfolder', str(staging),
            '-format', 'UDZO', '-fs', 'HFS+', str(output))
        run('hdiutil', 'verify', str(output))
        mount = root/'mounted'
        mount.mkdir()
        subprocess.run(['hdiutil', 'attach', '-readonly', '-nobrowse', '-mountpoint', str(mount), str(output)], check=True)
        try:
            assert (mount/'Applications').is_symlink()
            assert (mount/'Applications').readlink() == Path('/Applications')
            # Compare every regular resource and symlink, including all model weights.
            original, copied = app, mount/app.name
            source_entries = {p.relative_to(original) for p in original.rglob('*')}
            assert source_entries == {p.relative_to(copied) for p in copied.rglob('*')}
            for relative in source_entries:
                source, target = original/relative, copied/relative
                if source.is_symlink():
                    assert target.is_symlink() and source.readlink() == target.readlink(), relative
                elif source.is_file():
                    assert digest(source) == digest(target), relative
            run('codesign', '--verify', '--deep', '--strict', str(copied))
            info = plistlib.loads((copied/'Contents/Info.plist').read_bytes())
            print('Verified mounted app version:', info['CFBundleShortVersionString'])
        finally:
            run('hdiutil', 'detach', str(mount))
    checksum = output.with_name('OTONova-macOS-DMG-SHA256SUMS.txt')
    checksum.write_text(digest(output)+'  '+output.name+'\n', encoding='utf-8')
    print(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('app')
    parser.add_argument('output')
    arguments = parser.parse_args()
    package(arguments.app, arguments.output)
