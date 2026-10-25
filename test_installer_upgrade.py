"""Exercise replacement with an isolated fake payload; never touch Program Files."""

import os, subprocess, tempfile, unittest, zipfile, hashlib, struct, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COMPILER = Path("C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe")


@unittest.skipUnless(
    os.name == "nt" and COMPILER.exists(), "Windows .NET compiler required"
)
class InstallerUpgradeTests(unittest.TestCase):
    def test_replace_decline_corrupt_payload_and_destination_validation(self):
        with tempfile.TemporaryDirectory(
            prefix="OTONova installer upgrade "
        ) as temporary:
            root = Path(temporary).resolve()
            source = root / "installer.cs"
            code = (
                (ROOT / "tools/distribution_installer.cs")
                .read_text(encoding="utf-8")
                .replace("WFL-Oto", "OTONova")
            )
            source.write_text(code, encoding="utf-8-sig")
            required = re.findall(
                r'"([^"]+)"', re.search(r"Required=\{([^}]+)\}", code)[1]
            )
            payload = root / "payload.zip"
            with zipfile.ZipFile(payload, "w") as z:
                for name in required:
                    z.writestr(name, b"new installed file")
            raw = payload.read_bytes()
            valid = root / "setup.bin"
            bad = root / "corrupt.bin"
            valid.write_bytes(
                b"stub"
                + raw
                + hashlib.sha256(raw).digest()
                + struct.pack("<q", 4)
                + b"WFLOTO26"
            )
            bad.write_bytes(
                b"stub" + raw + b"0" * 32 + struct.pack("<q", 4) + b"WFLOTO26"
            )
            harness = root / "check.cs"
            harness.write_text(
                r"""using System;using System.IO;using System.Reflection;
class UpgradeTest {
 static object Call(string name,params object[] args) {
  try{return typeof(Installer).GetMethod(name,BindingFlags.NonPublic|BindingFlags.Static).Invoke(null,args);}
  catch(TargetInvocationException e){throw e.InnerException;}
 }
 [STAThread] static int Main(string[] args) {
  string area=Path.GetFullPath(args[2]),destination=Path.Combine(area,"OTONova");
  Directory.CreateDirectory(destination);
  File.WriteAllText(Path.Combine(destination,"OTONova.exe"),"old launcher");
  File.WriteAllText(Path.Combine(destination,"old.txt"),"keep on decline");
  Action<int,string> progress=(p,s)=>{};
  string expected=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86),"OTONova");
  if((string)Call("DefaultDestination")!=expected)throw new Exception("Default path mismatch");
  try {Call("Install",destination,false,progress);throw new Exception("Decline replaced existing files");}catch(IOException){}
  if(File.ReadAllText(Path.Combine(destination,"old.txt"))!="keep on decline")throw new Exception("Decline mutated old files");
  foreach(string invalid in new[]{Path.GetPathRoot(area),Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86)}) {
   try {Call("ValidateDestination",invalid);throw new Exception("Unsafe destination accepted");}catch(IOException){}
  }
  if(args[3]=="corrupt") {
   try {Call("Install",destination,true,progress);throw new Exception("Corrupt payload installed");}catch(IOException){}
   if(!File.Exists(Path.Combine(destination,"old.txt")))throw new Exception("Corruption removed old files");
  } else {
   Call("Install",destination,true,progress);
   if(File.Exists(Path.Combine(destination,"old.txt")))throw new Exception("Old files survived replacement");
   if(File.ReadAllText(Path.Combine(destination,"OTONova.exe"))!="new installed file")throw new Exception("New installation missing");
   string unknown=Path.Combine(area,"unrelated");Directory.CreateDirectory(unknown);File.WriteAllText(Path.Combine(unknown,"user.txt"),"keep");
   try {Call("Install",unknown,true,progress);throw new Exception("Unrelated folder replaced");}catch(IOException){}
   if(!File.Exists(Path.Combine(unknown,"user.txt")))throw new Exception("Unrelated data removed");
  }
  foreach(string path in Directory.GetDirectories(area,".OTONova-*"))throw new Exception("Temporary installation left behind: "+path);
  Console.WriteLine("passed");return 0;
 }
}
""",
                encoding="utf-8-sig",
            )
            executable = root / "check.exe"
            subprocess.run(
                [
                    str(COMPILER),
                    "/nologo",
                    "/target:exe",
                    "/define:VERIFY_BUILD",
                    "/main:UpgradeTest",
                    "/reference:System.Windows.Forms.dll",
                    "/reference:System.Drawing.dll",
                    "/reference:System.IO.Compression.dll",
                    "/out:" + str(executable),
                    str(source),
                    str(harness),
                ],
                check=True,
                capture_output=True,
            )
            for mode, setup in [("valid", valid), ("corrupt", bad)]:
                area = root / mode
                area.mkdir()
                result = subprocess.run(
                    [str(executable), "/check", str(setup), str(area), mode],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                self.assertIn("passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
