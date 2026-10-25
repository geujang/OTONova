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
    static string Self {get{
#if VERIFY_BUILD
        return Environment.GetCommandLineArgs()[2];
#else
        return Process.GetCurrentProcess().MainModule.FileName;
#endif
    }}
    static string DefaultDestination() {
        return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86),"WFL-Oto");
    }
    static string ValidateDestination(string destination) {
        if(String.IsNullOrWhiteSpace(destination) || !Path.IsPathRooted(destination))throw new IOException("설치할 전체 경로를 지정해주세요.");
        string root=Path.GetFullPath(destination).TrimEnd(Path.DirectorySeparatorChar,Path.AltDirectorySeparatorChar);
        string[] forbidden={Path.GetPathRoot(root),Environment.GetFolderPath(Environment.SpecialFolder.Windows),
            Environment.GetFolderPath(Environment.SpecialFolder.System),Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),
            Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86),Environment.GetFolderPath(Environment.SpecialFolder.UserProfile)};
        foreach(string path in forbidden)if(!String.IsNullOrEmpty(path) && String.Equals(root,path.TrimEnd('\\','/'),StringComparison.OrdinalIgnoreCase))
            throw new IOException("드라이브 또는 시스템 폴더 자체에는 설치할 수 없습니다. OTONova 전용 하위 폴더를 지정해주세요.");
        for(var dir=new DirectoryInfo(root);dir!=null;dir=dir.Parent)
            if(dir.Exists && (dir.Attributes & FileAttributes.ReparsePoint)!=0)throw new IOException("링크 또는 연결 폴더에는 설치할 수 없습니다.");
        if(Self.StartsWith(root+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase))throw new IOException("설치 파일을 설치 대상 폴더 밖으로 옮겨 실행해주세요.");
        return root;
    }
    static bool HasFiles(string root) {return Directory.Exists(root) && Directory.GetFileSystemEntries(root).Length>0;}
    static void ValidateExistingInstallation(string root) {
        if(!HasFiles(root))return;
        if(!File.Exists(Path.Combine(root,"WFL-Oto.exe")) && !File.Exists(Path.Combine(root,"OtoNova.exe")))
            throw new IOException("기존 프로그램 설치 폴더를 확인할 수 없습니다. OTONova 전용 폴더를 지정해주세요.");
        ValidateRemovalTree(root);
        foreach(var process in Process.GetProcesses()) {
            try {
                string executable=process.MainModule.FileName;
                if(executable.StartsWith(root+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase))
                    throw new IOException("OTONova가 실행 중입니다. 프로그램을 종료한 뒤 다시 설치해주세요.");
            }catch(System.ComponentModel.Win32Exception){}catch(InvalidOperationException){}finally{process.Dispose();}
        }
    }
    static void ValidateRemovalTree(string root) {
        if((File.GetAttributes(root)&FileAttributes.ReparsePoint)!=0)throw new IOException("기존 설치에 링크가 있어 교체할 수 없습니다.");
        if(!Directory.Exists(root))return;
        foreach(string path in Directory.GetFileSystemEntries(root))ValidateRemovalTree(path);
    }
    static void RemoveInstallationTree(string root,string parent) {
        string full=Path.GetFullPath(root),container=Path.GetFullPath(parent).TrimEnd('\\','/')+Path.DirectorySeparatorChar;
        if(!full.StartsWith(container,StringComparison.OrdinalIgnoreCase) || String.Equals(full.TrimEnd('\\','/'),container.TrimEnd('\\','/'),StringComparison.OrdinalIgnoreCase))
            throw new IOException("삭제 경로가 설치 작업 폴더 밖에 있습니다.");
        ValidateRemovalTree(full);
        foreach(string path in Directory.GetFileSystemEntries(full)) {
            if(Directory.Exists(path))RemoveInstallationTree(path,full);
            else {File.SetAttributes(path,FileAttributes.Normal);File.Delete(path);}
        }
        Directory.Delete(full);
    }
    static void Install(string destination,bool replace,Action<int,string> progress) {
        string root=ValidateDestination(destination);
        ValidateExistingInstallation(root);
        if(HasFiles(root) && !replace)throw new IOException("기존 설치 교체에 동의하지 않았습니다.");
        string parent=Path.GetDirectoryName(root);
        string staging=Path.Combine(parent,".OTONova-install-"+Guid.NewGuid().ToString("N"));
        string backup=Path.Combine(parent,".OTONova-previous-"+Guid.NewGuid().ToString("N"));
        bool previousMoved=false,installed=false;
        try {
            // Validate and fully extract the new payload before touching the previous installation.
            Extract(staging,progress);
            ValidateExistingInstallation(root);
            if(Directory.Exists(root)) {Directory.Move(root,backup);previousMoved=true;}
            try {Directory.Move(staging,root);installed=true;}
            catch {if(previousMoved)Directory.Move(backup,root);previousMoved=false;throw;}
            if(previousMoved)RemoveInstallationTree(backup,parent);
            progress(100,"설치 완료");
        } finally {
            if(!installed && Directory.Exists(staging))RemoveInstallationTree(staging,parent);
        }
    }
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
        var form=new Form {Text="WFL-Oto "+Version+" Setup",ClientSize=new Size(720,460),StartPosition=FormStartPosition.CenterScreen,FormBorderStyle=FormBorderStyle.FixedDialog,MaximizeBox=false,Font=new Font("Malgun Gothic",10),BackColor=Color.White};
        try {form.Icon=Icon.ExtractAssociatedIcon(Self);}catch{}
        var side=new Panel {Dock=DockStyle.Left,Width=170,BackColor=Color.FromArgb(51,23,85)};
        side.Controls.Add(new Label {Left=18,Top=30,Width=145,Height=80,Text="WFL-Oto\n"+Version,ForeColor=Color.FromArgb(222,193,255),Font=new Font("Segoe UI",18,FontStyle.Bold)});
        var steps=new Label {Left=18,Top=150,Width=145,Height=220,ForeColor=Color.White};side.Controls.Add(steps);
        var title=new Label {Left=196,Top=28,Width=495,Height=40,Font=new Font("Malgun Gothic",15,FontStyle.Bold)};
        var body=new Label {Left=198,Top=84,Width=490,Height=150};
        var path=new TextBox {Left=198,Top=240,Width=380,Text=DefaultDestination()};
        var browse=new Button {Left=588,Top=238,Width=100,Height=30,Text="찾아보기"};
        var desktopShortcut=new CheckBox {Left=198,Top=240,Width=480,Height=30,Text="바탕화면 바로가기 만들기",Checked=true};
        var launch=new CheckBox {Left=198,Top=240,Width=480,Height=30,Text="WFL-Oto 실행",Checked=true};
        var status=new Label {Left=198,Top=280,Width=490,Height=70,AutoEllipsis=true};
        var bar=new ProgressBar {Left=198,Top=242,Width=490,Height=23};
        var back=new Button {Left=394,Top=402,Width=94,Height=34,Text="< 이전"};
        var next=new Button {Left=494,Top=402,Width=94,Height=34,Text="다음 >"};
        var cancel=new Button {Left=594,Top=402,Width=94,Height=34,Text="취소"};
        form.Controls.AddRange(new Control[]{side,title,body,path,browse,desktopShortcut,launch,status,bar,back,next,cancel});
        int page=0;bool running=false,replace=false;string destination=null;
        Action render=()=>{
            steps.Text="1  시작\n\n2  설치 위치\n\n3  추가 옵션\n\n4  설치 확인\n\n5  설치\n\n6  완료";
            path.Visible=browse.Visible=page==1;desktopShortcut.Visible=page==2;launch.Visible=page==5;
            bar.Visible=status.Visible=page==4;back.Visible=page<4;back.Enabled=page>0;
            next.Enabled=!running;cancel.Enabled=!running;next.Text=page==3?"설치":page==5?"완료":"다음 >";
            if(page==0){title.Text="설치 마법사에 오신 것을 환영합니다";body.Text="WFL-Oto "+Version+"을 컴퓨터에 설치합니다.\n\n일본어·한국어·영어 자동 원설에 필요한 프로그램과 모델이 포함되어 있습니다.\n\n계속하려면 다음을 누르세요.";}
            if(page==1){title.Text="설치 위치 선택";body.Text="프로그램을 설치할 폴더를 선택하세요.\n\n기본 경로를 사용하거나 찾아보기로 변경할 수 있습니다.\n(약 2.5GB 필요)";}
            if(page==2){title.Text="추가 옵션 선택";body.Text="설치할 때 사용할 추가 옵션을 선택하세요.";}
            if(page==3){title.Text="설치 준비 완료";body.Text="아래 설정으로 설치합니다.\n\n설치 위치:\n"+destination+"\n\n바탕화면 바로가기: "+(desktopShortcut.Checked?"만들기":"만들지 않음")+(replace?"\n\n기존 설치를 새 버전으로 교체합니다.":"");}
            if(page==4){title.Text="설치 중";body.Text="프로그램과 모델을 설치하고 있습니다.\n설치가 끝날 때까지 기다려주세요.";}
            if(page==5){title.Text="설치 완료";body.Text="WFL-Oto "+Version+" 설치를 완료했습니다.\n\n완료를 누르면 설치 마법사를 닫습니다.";cancel.Visible=false;}
        };
        browse.Click+=(s,e)=>{using(var dialog=new FolderBrowserDialog()){if(dialog.ShowDialog(form)==DialogResult.OK)path.Text=Path.Combine(dialog.SelectedPath,"WFL-Oto");}};
        form.FormClosing+=(s,e)=>{if(running)e.Cancel=true;};
        cancel.Click+=(s,e)=>form.Close();
        back.Click+=(s,e)=>{if(page>0){page--;render();}};
        next.Click+=async (s,e)=>{
            if(page==5){
                if(launch.Checked)try {Process.Start(new ProcessStartInfo(Path.Combine(destination,"WFL-Oto.exe")){WorkingDirectory=destination,UseShellExecute=true});}
                catch(Exception error){MessageBox.Show(form,error.Message,"실행 오류",MessageBoxButtons.OK,MessageBoxIcon.Warning);}
                form.Close();return;
            }
            if(page==1){
                try {
                    destination=ValidateDestination(path.Text);ValidateExistingInstallation(destination);replace=false;
                    if(HasFiles(destination)){
                        if(MessageBox.Show(form,"기존 설치를 덮어쓰시겠습니까?\n선택한 폴더의 기존 파일을 모두 제거하고 새 버전을 설치합니다.\n\n"+destination,"기존 설치 교체",MessageBoxButtons.YesNo,MessageBoxIcon.Question,MessageBoxDefaultButton.Button2)!=DialogResult.Yes)return;
                        replace=true;
                    }
                }catch(Exception error){MessageBox.Show(form,error.Message,"설치 경로 확인",MessageBoxButtons.OK,MessageBoxIcon.Warning);return;}
            }
            if(page!=3){page++;render();return;}
            page=4;running=true;bar.Value=0;status.Text="설치 준비 중…";render();
            bool createShortcut=desktopShortcut.Checked;
            try {
                await Task.Run(()=>Install(destination,replace,(percent,message)=>form.BeginInvoke((Action)(()=>{bar.Value=percent;status.Text=message;}))));
                if(createShortcut)try {CreateDesktopShortcut(destination,Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory));}
                catch(Exception error){MessageBox.Show(form,"설치는 완료했지만 바탕화면 바로가기를 만들지 못했습니다.\n"+error.Message,"바로가기 생성 오류",MessageBoxButtons.OK,MessageBoxIcon.Warning);}
                running=false;page=5;render();
            }catch(Exception error){running=false;page=3;render();MessageBox.Show(form,error.Message,"설치 오류",MessageBoxButtons.OK,MessageBoxIcon.Error);}
        };
        form.AcceptButton=next;form.CancelButton=cancel;render();Application.Run(form);return 0;
    }
}
