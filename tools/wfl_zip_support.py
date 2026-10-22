"""Let zipped Python modules share package paths with native DLL/PYD files."""
import importlib.machinery
import os
import sys
import zipfile

BASE = os.path.dirname(__file__)
ARCHIVE = os.path.join(BASE, 'wfl-code.zip')
with zipfile.ZipFile(ARCHIVE) as stream:
    ROOTS = {name.split('/')[0] for name in stream.namelist() if '/' in name and not name.split('/')[0].endswith('.dist-info')}


class MixedPackageFinder:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.partition('.')[0] not in ROOTS:
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path, target)
        if spec is None or spec.submodule_search_locations is None:
            return None
        # Keep source-anchor files and binary extensions on disk. Other Python
        # modules load directly from ZIP without extracting or writing caches.
        for location in (os.path.join(ARCHIVE, *fullname.split('.')),
                         os.path.join(BASE, *fullname.split('.'))):
            if location not in spec.submodule_search_locations:
                spec.submodule_search_locations.append(location)
        return spec


sys.meta_path.insert(sys.meta_path.index(importlib.machinery.PathFinder), MixedPackageFinder())
