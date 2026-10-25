using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Windows.Forms;
using System.Reflection;
[assembly: AssemblyTitle("OTONova")]
[assembly: AssemblyProduct("OTONova")]
[assembly: AssemblyDescription("OTONova V2.0 자동 원설기")]
[assembly: AssemblyVersion("2.0.0.0")]

static class Launcher {
    // Quote using Windows' CommandLineToArgvW backslash rules.
    static string Quote(string value) {
        var text=new StringBuilder("\"");int slashes=0;
        foreach(char c in value) {
            if(c=='\\') {slashes++;continue;}
            if(c=='\"') {text.Append('\\',slashes*2+1);text.Append(c);slashes=0;continue;}
            text.Append('\\',slashes);slashes=0;text.Append(c);
        }
        text.Append('\\',slashes*2);return text.Append('"').ToString();
    }
    [STAThread] static int Main(string[] args) {
        try {
            string root=AppDomain.CurrentDomain.BaseDirectory;
            var command=new StringBuilder("-B -s "+Quote(Path.Combine(root,"app_bootstrap.py")));
            foreach(string arg in args) command.Append(" ").Append(Quote(arg));
            var info=new ProcessStartInfo(Path.Combine(root,"runtime","pythonw.exe"),command.ToString());
            info.WorkingDirectory=root;info.UseShellExecute=false;info.CreateNoWindow=true;
            info.EnvironmentVariables["PYTHONPATH"]="";
            info.EnvironmentVariables.Remove("PYTHONHOME");
            info.EnvironmentVariables["PYTHONDONTWRITEBYTECODE"]="1";
            using(var process=Process.Start(info)) {
                process.WaitForExit();
                if(process.ExitCode!=0 && args.Length==0)
                    MessageBox.Show("실행 오류입니다. "+Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"OTONova","Logs","wfl-gui.log")+" 파일을 확인해주세요.","OTONova");
                return process.ExitCode;
            }
        } catch(Exception error) {
            MessageBox.Show(error.ToString(),"OTONova 실행 오류");return 1;
        }
    }
}
