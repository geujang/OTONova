import hashlib,io,json,os,struct,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
import platform_support as platform
from prepare_macos_models import prepare,WEIGHTS
class PlatformTests(unittest.TestCase):
 def test_frozen_mac_uses_same_executable_as_worker(self):
  command=platform.backend_command('/app/Resources','/app/Resources','/app/Resources/WFL','/app/Resources/Japanese',platform='darwin',frozen=True,executable='/app/MacOS/OTONova')
  self.assertEqual(command,['/app/MacOS/OTONova','--wfl-backend','/app/Resources/WFL','/app/Resources/Japanese'])
 def test_source_mac_falls_back_to_current_python(self):
  with tempfile.TemporaryDirectory() as folder:
   command=platform.backend_command(folder,folder,'model','ja',platform='darwin',frozen=False,executable='/usr/bin/python3')
   self.assertEqual(Path(command[0]),Path('/usr/bin/python3'))
   self.assertEqual(command[1:3],['-B','-I'])
   self.assertTrue(command[3].endswith('wfl_backend.py'))
 def test_logs_outside_app_bundle(self):
  self.assertEqual(platform.log_directory('darwin',Path('/Users/test')),Path('/Users/test/Library/Logs/OTONova'))
 def test_frozen_resources_are_model_workspace(self):
  with tempfile.TemporaryDirectory() as folder:
   base=Path(folder);(base/'Japanese').mkdir();(base/'Japanese/phonemes.txt').write_text('B-a')
   with patch.object(platform.sys,'_MEIPASS',folder,create=True):self.assertEqual(platform.workspace(),base)
 def test_model_extraction_verifies_checksum_and_preserves_existing_weights(self):
  with tempfile.TemporaryDirectory() as folder:
   folder=Path(folder);memory=io.BytesIO()
   with zipfile.ZipFile(memory,'w') as archive:
    for name in WEIGHTS:archive.writestr(name,b'model-data')
    archive.writestr('../unsafe',b'never extracted');archive.writestr('runtime/python.exe',b'not a Mac runtime')
   payload=memory.getvalue();prefix=b'fake installer stub'
   raw=prefix+payload+hashlib.sha256(payload).digest()+struct.pack('<Q',len(prefix))+b'WFLOTO26'
   installer=folder/'setup.exe';installer.write_bytes(raw);target=folder/'models';digest=hashlib.sha256(raw).hexdigest()
   with self.assertRaises(ValueError):prepare(installer,target,'0'*64)
   self.assertFalse(target.exists());prepare(installer,target,digest)
   self.assertEqual(len(list(target.rglob('*.ckpt'))),3)
   self.assertFalse((target/'runtime').exists());self.assertFalse((folder/'unsafe').exists())
   prepare(installer,target,digest)
   (target/WEIGHTS[0]).write_bytes(b'custom model')
   with self.assertRaises(FileExistsError):prepare(installer,target,digest)
   self.assertEqual((target/WEIGHTS[0]).read_bytes(),b'custom model')
if __name__=='__main__':unittest.main()
