using System;
using System.IO;
using System.IO.Compression;
using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;
using System.Drawing;

sealed class PayloadStream : Stream {
    readonly Stream source; readonly long start, length;
    public PayloadStream(Stream source, long start, long length) { this.source=source;this.start=start;this.length=length;Position=0; }
    public override bool CanRead { get {return true;} } public override bool CanSeek {get{return true;}}
    public override bool CanWrite {get{return false;}} public override long Length {get{return length;}}
    public override long Position {get{return source.Position-start;}set {if(value<0 || value>length)throw new IOException();source.Position=start+value;}}
    public override int Read(byte[] b,int o,int n) {return source.Read(b,o,(int)Math.Min(n,length-Position));}
    public override long Seek(long o,SeekOrigin origin) {Position=(origin==SeekOrigin.Begin?0:origin==SeekOrigin.Current?Position:length)+o;return Position;}
    public override void Flush() {} public override void SetLength(long n){throw new NotSupportedException();}
    public override void Write(byte[] b,int o,int n){throw new NotSupportedException();}
}

static class Installer {
    const string Version="v27";
    static readonly string[] Required={"WFL-Oto.exe","runtime/python.exe","English/last.ckpt","Japanese/last.ckpt","WFL/Archivoice/korean/last.ckpt","WFL/encoder/encoder.pt","_internal/assets/reclist-signatures.json","_internal/assets/arpasing-catalog.json.gz","validation.json"};
    static string Self {get{return Process.GetCurrentProcess().MainModule.FileName;}}
    static void Extract(string destination,Action<int,string> progress) {
        if(destination!=null && Directory.Exists(destination) && Directory.GetFileSystemEntries(destination).Length>0)
            throw new IOException("비어 있는 새 설치 폴더를 지정해주세요. 기존 파일은 덮어쓰지 않습니다.");
        using(var file=File.OpenRead(Self)) {
            file.Position=file.Length-48;
            var reader=new BinaryReader(file);byte[] expected=reader.ReadBytes(32);long start=reader.ReadInt64();
            if(Encoding.ASCII.GetString(reader.ReadBytes(8))!="WFLOTO26" || start<0 || start>=file.Length-48)throw new IOException("설치 데이터가 손상되었습니다.");
            using(var payload=new PayloadStream(file,start,file.Length-start-48)) {
                progress(0,"설치파일 무결성 확인 중…");
                byte[] actual;using(var hash=SHA256.Create())actual=hash.ComputeHash(payload);
                for(int i=0;i<32;i++)if(expected[i]!=actual[i])throw new IOException("설치파일 검증 실패: 파일을 다시 받아주세요.");
                payload.Position=0;
                using(var zip=new ZipArchive(payload,ZipArchiveMode.Read,true)) {
                    foreach(string name in Required)if(zip.GetEntry(name)==null)throw new IOException("필수 파일 누락: "+name);
                    if(destination==null)return;
                    string root=Path.GetFullPath(destination).TrimEnd(Path.DirectorySeparatorChar)+Path.DirectorySeparatorChar;
                    long total=0,done=0;foreach(var entry in zip.Entries)total+=entry.Length;
                    Directory.CreateDirectory(root);DateTime last=DateTime.MinValue;byte[] buffer=new byte[1024*1024];
                    foreach(var entry in zip.Entries) {
                        string target=Path.GetFullPath(Path.Combine(root,entry.FullName.Replace('/',Path.DirectorySeparatorChar)));
                        if(!target.StartsWith(root,StringComparison.OrdinalIgnoreCase))throw new IOException("잘못된 파일 경로입니다.");
                        if(entry.FullName.EndsWith("/")){Directory.CreateDirectory(target);continue;}
                        Directory.CreateDirectory(Path.GetDirectoryName(target));
                        using(var input=entry.Open())using(var output=new FileStream(target,FileMode.CreateNew,FileAccess.Write)) {
                            int count;while((count=input.Read(buffer,0,buffer.Length))>0) {
                                output.Write(buffer,0,count);done+=count;
                                if((DateTime.UtcNow-last).TotalMilliseconds>150){progress((int)(done*100/Math.Max(1,total)),entry.FullName);last=DateTime.UtcNow;}
                            }
                        }
                    }
                    progress(100,"설치 완료");
                }
            }
        }
    }
    static void CreateDesktopShortcut(string destination, string desktop) {
        string folder=Path.GetFullPath(destination);
        string executable=Path.Combine(folder,"WFL-Oto.exe");
        if(!File.Exists(executable))throw new FileNotFoundException("실행 파일을 찾을 수 없습니다.",executable);
        Directory.CreateDirectory(desktop);
        object shell=null,shortcut=null;
        try {
            shell=Activator.CreateInstance(Type.GetTypeFromProgID("WScript.Shell",true));
            shortcut=shell.GetType().InvokeMember("CreateShortcut",System.Reflection.BindingFlags.InvokeMethod,null,shell,
                new object[]{Path.Combine(desktop,"WFL-Oto.lnk")});
            var type=shortcut.GetType();
            type.InvokeMember("TargetPath",System.Reflection.BindingFlags.SetProperty,null,shortcut,new object[]{executable});
            type.InvokeMember("WorkingDirectory",System.Reflection.BindingFlags.SetProperty,null,shortcut,new object[]{folder});
            type.InvokeMember("IconLocation",System.Reflection.BindingFlags.SetProperty,null,shortcut,new object[]{executable+",0"});
            type.InvokeMember("Description",System.Reflection.BindingFlags.SetProperty,null,shortcut,new object[]{"WFL-Oto"});
            type.InvokeMember("Save",System.Reflection.BindingFlags.InvokeMethod,null,shortcut,null);
        } finally {
            if(shortcut!=null)System.Runtime.InteropServices.Marshal.FinalReleaseComObject(shortcut);
            if(shell!=null)System.Runtime.InteropServices.Marshal.FinalReleaseComObject(shell);
        }
    }
    [STAThread] static int Main(string[] args) {
        if(args.Length>0) {
            try {
                if(args[0]=="/verify")Extract(null,(p,s)=>{});
                else if(args[0]=="/extract" && args.Length==2)Extract(args[1],(p,s)=>{});
                else return 2;
                return 0;
            }catch(Exception e){Console.Error.WriteLine(e.ToString());return 1;}
        }
        Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);
        var form=new Form {Text="WFL-Oto "+Version+" 설치",ClientSize=new Size(620,255),StartPosition=FormStartPosition.CenterScreen,FormBorderStyle=FormBorderStyle.FixedDialog,MaximizeBox=false,Font=new Font("Malgun Gothic",10)};
        var intro=new Label {Left=18,Top=18,Width=584,Height=42,Text="프로그램과 일본어·한국어·영어 보조 모델을 설치합니다.\n설치 후 WFL-Oto.exe를 실행합니다. (약 2.5GB 필요)"};
        var path=new TextBox {Left=18,Top=73,Width=485,Text=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"Programs","WFL-Oto-"+Version)};
        var browse=new Button {Left=512,Top=71,Width=90,Height=30,Text="찾아보기"};
        var status=new Label {Left=18,Top=111,Width=584,Height=24,Text="설치할 새 폴더를 지정하세요."};
        var bar=new ProgressBar {Left=18,Top=142,Width=584,Height=19};
        var desktopShortcut=new CheckBox {Left=18,Top=174,Width=370,Height=26,Text="바탕화면 바로가기 만들기",Checked=true};
        var install=new Button {Left=487,Top=210,Width=115,Height=32,Text="설치 및 실행"};
        bool running=false;
        browse.Click+=(s,e)=>{using(var dialog=new FolderBrowserDialog()){if(dialog.ShowDialog(form)==DialogResult.OK)path.Text=Path.Combine(dialog.SelectedPath,"WFL-Oto-"+Version);}};
        form.FormClosing+=(s,e)=>{if(running)e.Cancel=true;};
        install.Click+=async (s,e)=>{
            string destination=path.Text;
            running=true;install.Enabled=browse.Enabled=path.Enabled=desktopShortcut.Enabled=false;
            bool createShortcut=desktopShortcut.Checked;
            try {
                await Task.Run(()=>Extract(destination,(percent,message)=>form.BeginInvoke((Action)(()=>{bar.Value=percent;status.Text=message;}))));
                if(createShortcut) {
                    try {CreateDesktopShortcut(destination,Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory));}
                    catch(Exception shortcutError) {MessageBox.Show(form,"설치는 완료했지만 바탕화면 바로가기를 만들지 못했습니다.\n"+shortcutError.Message,"바로가기 생성 오류",MessageBoxButtons.OK,MessageBoxIcon.Warning);}
                }
                running=false;
                Process.Start(new ProcessStartInfo(Path.Combine(destination,"WFL-Oto.exe")){WorkingDirectory=destination,UseShellExecute=true});
                form.Close();
            } catch(Exception error) {
                running=false;install.Enabled=browse.Enabled=path.Enabled=desktopShortcut.Enabled=true;
                MessageBox.Show(form,error.Message,"설치 오류",MessageBoxButtons.OK,MessageBoxIcon.Error);
                status.Text="설치 오류: 경로와 남은 공간을 확인해주세요.";
            }
        };
        form.Controls.AddRange(new Control[]{intro,path,browse,status,bar,desktopShortcut,install});Application.Run(form);return 0;
    }
}
