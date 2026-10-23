"""Track external WAV/oto changes without touching project or alignment data."""
from pathlib import Path
from project_store import signature

def snapshot(folder,kind=None):
    root=Path(folder);result={}
    for path in root.rglob('*'):
        if not path.is_file():continue
        category='wav' if path.suffix.lower()=='.wav' else 'oto' if path.name.lower()=='oto.ini' else None
        if category is None or kind and category!=kind:continue
        try:result[path.relative_to(root).as_posix()]={'kind':category,'signature':signature(path)}
        except OSError:continue
    return result

def changes(before,after):
    result={'wav':[],'oto':[]}
    for name in sorted(set(before)|set(after)):
        if before.get(name)!=after.get(name):result[(after.get(name) or before[name])['kind']].append(name)
    return result
