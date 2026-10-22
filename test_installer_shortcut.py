"""Compile the installer helper and verify real shortcuts in a temporary desktop."""
import os,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent
COMPILER=Path('C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe')
@unittest.skipUnless(os.name=='nt' and COMPILER.exists(),'Requires Windows shell and .NET compiler')
class InstallerShortcutTests(unittest.TestCase):
 def test_shortcut_target_working_directory_icon_and_retry(self):
  with tempfile.TemporaryDirectory(prefix='OtoNova shortcut ') as temporary:
   folder=Path(temporary)
   installer=folder/'installer.cs'
   installer.write_text((ROOT/'tools/distribution_installer.cs').read_text(encoding='utf-8').replace('WFL-Oto','OtoNova'),encoding='utf-8-sig')
   harness=folder/'check.cs'
   harness.write_text(r'''
using System;using System.IO;using System.Reflection;using System.Runtime.InteropServices;
class ShortcutTest {
 [STAThread] static int Main(string[] args) {
  string install=Path.Combine(args[0],"음원 프로그램"),desktop=Path.Combine(args[0],"가상 바탕화면");
  Directory.CreateDirectory(install);File.WriteAllBytes(Path.Combine(install,"OtoNova.exe"),new byte[]{0});
  var method=typeof(Installer).GetMethod("CreateDesktopShortcut",BindingFlags.NonPublic|BindingFlags.Static);
  for(int attempt=0;attempt<2;attempt++)method.Invoke(null,new object[]{install,desktop});
  string link=Path.Combine(desktop,"OtoNova.lnk");if(!File.Exists(link))throw new Exception("Shortcut missing");
  object shell=Activator.CreateInstance(Type.GetTypeFromProgID("WScript.Shell",true));
  object shortcut=shell.GetType().InvokeMember("CreateShortcut",BindingFlags.InvokeMethod,null,shell,new object[]{link});
  try {
   var t=shortcut.GetType();
   string target=(string)t.InvokeMember("TargetPath",BindingFlags.GetProperty,null,shortcut,null);
   string working=(string)t.InvokeMember("WorkingDirectory",BindingFlags.GetProperty,null,shortcut,null);
   string icon=(string)t.InvokeMember("IconLocation",BindingFlags.GetProperty,null,shortcut,null);
   if(!String.Equals(target,Path.Combine(install,"OtoNova.exe"),StringComparison.OrdinalIgnoreCase))throw new Exception(target);
   if(!String.Equals(working,install,StringComparison.OrdinalIgnoreCase))throw new Exception(working);
   if(!icon.StartsWith(target,StringComparison.OrdinalIgnoreCase))throw new Exception(icon);
  }finally{Marshal.FinalReleaseComObject(shortcut);Marshal.FinalReleaseComObject(shell);}
  try {method.Invoke(null,new object[]{Path.Combine(args[0],"missing"),Path.Combine(args[0],"untouched")});throw new Exception("Missing exe accepted");}
  catch(TargetInvocationException e){if(!(e.InnerException is FileNotFoundException))throw;}
  if(Directory.Exists(Path.Combine(args[0],"untouched")))throw new Exception("Unexpected desktop mutation");
  Console.WriteLine("Shortcut target, working directory, icon, repeat creation and missing target passed");return 0;
 }
}
''',encoding='utf-8-sig')
   exe=folder/'check.exe'
   subprocess.run([str(COMPILER),'/nologo','/target:exe','/main:ShortcutTest','/reference:System.Windows.Forms.dll','/reference:System.Drawing.dll','/reference:System.IO.Compression.dll','/out:'+str(exe),str(installer),str(harness)],check=True,capture_output=True)
   result=subprocess.run([str(exe),str(folder)],check=True,capture_output=True,text=True)
   self.assertIn('passed',result.stdout)
if __name__=='__main__':unittest.main()
