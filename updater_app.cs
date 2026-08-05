// Commemorate 独立更新程序
// 用法:
//   updater.exe --target <旧exe路径> --source <新exe路径> --tmp <临时解压目录>
//              --log <日志文件> [--old-pid <旧进程PID>] [--name <进程名>]
//
// 流程: 等待旧进程退出 → 替换 exe → 等待杀毒安定 → 干净环境启动新版本
//       → 验证新版本确实完成解压，失败自动重试 → 清理临时目录
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Threading;

class CommemorateUpdater
{
    static string _logFile = "";

    static void Log(string msg)
    {
        try
        {
            File.AppendAllText(_logFile,
                string.Format("[{0:yyyy-MM-dd HH:mm:ss.fff}] {1}\r\n",
                    DateTime.Now, msg));
        }
        catch { }
    }

    static string GetArg(string[] args, string key)
    {
        for (int i = 0; i < args.Length - 1; i++)
            if (args[i] == key)
                return args[i + 1];
        return null;
    }

    static int Main(string[] args)
    {
        Console.OutputEncoding = Encoding.UTF8;

        string target = GetArg(args, "--target");
        string source = GetArg(args, "--source");
        string tmpDir = GetArg(args, "--tmp");
        _logFile = GetArg(args, "--log");
        string oldPidStr = GetArg(args, "--old-pid");
        string exeName = GetArg(args, "--name");

        if (string.IsNullOrEmpty(target) || string.IsNullOrEmpty(source) ||
            string.IsNullOrEmpty(_logFile))
        {
            Console.WriteLine("用法: updater.exe --target <exe> --source <exe> " +
                              "--tmp <dir> --log <file> [--old-pid <pid>] [--name <name>]");
            return 2;
        }

        Log("updater started");
        Log("target=" + target);
        Log("source=" + source);

        // 1. 等待旧进程完全退出
        int pid = 0;
        int.TryParse(oldPidStr ?? "", out pid);
        if (pid > 0 && WaitForPidExit(pid, 60))
        {
            Log("old process exited (pid " + pid + ")");
        }
        else if (pid > 0)
        {
            Log("old process did not exit in 60s, force killing");
            KillByName(exeName);
        }
        else
        {
            WaitForNameGone(exeName, 60);
        }

        // 多等 1 秒，确保旧进程的 PyInstaller 临时目录清理完成
        Thread.Sleep(1000);

        // 2. 替换 exe（带重试与大小校验）
        if (!ReplaceFile(source, target))
        {
            Log("ERROR: replace failed");
            Console.WriteLine("文件替换失败，请关闭杀毒软件后手动更新。");
            return 1;
        }
        Log("replace ok");

        // 3. 等 3 秒，避开杀毒软件对刚写入文件的实时扫描
        Thread.Sleep(3000);

        // 4. 干净环境启动新版本；失败自动重试
        bool launched = false;
        for (int i = 1; i <= 3; i++)
        {
            Log("launch attempt " + i);
            if (LaunchAndVerify(target))
            {
                Log("new version launched");
                Console.WriteLine("新版本已启动");
                launched = true;
                break;
            }
            if (i < 3)
            {
                Log("launch may have failed, cleaning and retrying");
                KillByName(exeName);
                Thread.Sleep(3000);
            }
        }
        if (!launched)
            Log("ERROR: all launch attempts failed");

        // 5. 清理临时解压目录
        if (!string.IsNullOrEmpty(tmpDir) && Directory.Exists(tmpDir))
        {
            try { Directory.Delete(tmpDir, true); }
            catch (Exception e) { Log("cleanup tmp error: " + e.Message); }
        }

        Log("updater done");
        return launched ? 0 : 3;
    }

    // 等待指定 PID 退出（进程已不存在视为已退出）
    static bool WaitForPidExit(int pid, int timeoutSec)
    {
        try
        {
            Process p = Process.GetProcessById(pid);
            return p.WaitForExit(timeoutSec * 1000);
        }
        catch (ArgumentException) { return true; }
        catch (Exception) { return true; }
    }

    static void KillByName(string name)
    {
        if (string.IsNullOrEmpty(name))
            return;
        try
        {
            foreach (Process p in Process.GetProcessesByName(name))
            {
                try { p.Kill(); p.WaitForExit(5000); }
                catch { }
            }
        }
        catch { }
    }

    static void WaitForNameGone(string name, int timeoutSec)
    {
        if (string.IsNullOrEmpty(name))
            return;
        Stopwatch sw = Stopwatch.StartNew();
        while (sw.Elapsed.TotalSeconds < timeoutSec)
        {
            if (Process.GetProcessesByName(name).Length == 0)
                return;
            Thread.Sleep(1000);
        }
        KillByName(name);
    }

    static bool ReplaceFile(string source, string target)
    {
        for (int i = 0; i < 5; i++)
        {
            try
            {
                File.Copy(source, target, true);
                FileInfo s = new FileInfo(source);
                FileInfo t = new FileInfo(target);
                if (s.Length == t.Length)
                    return true;
                Log("size mismatch, retry");
            }
            catch (Exception e)
            {
                Log("copy error: " + e.Message);
            }
            Thread.Sleep(1000);
        }
        return false;
    }

    static HashSet<string> SnapshotMeiDirs()
    {
        var set = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        try
        {
            foreach (string dir in Directory.GetDirectories(Path.GetTempPath(), "_MEI*"))
                set.Add(dir);
        }
        catch { }
        return set;
    }

    static bool LaunchAndVerify(string target)
    {
        try
        {
            // 从当前进程环境彻底移除 _MEIPASS2，子进程不再继承旧进程临时目录
            Environment.SetEnvironmentVariable("_MEIPASS2", null);

            var before = SnapshotMeiDirs();
            var psi = new ProcessStartInfo();
            psi.FileName = target;
            psi.WorkingDirectory = Path.GetDirectoryName(target) ?? "";
            // 必须用 UseShellExecute=true（由 shell 启动，等价于双击）。
            // UseShellExecute=false 会让窗口版 PyInstaller 程序继承父进程
            // 控制台句柄，导致解压 python DLL 失败（Failed to load Python DLL）。
            psi.UseShellExecute = true;
            Process p = Process.Start(psi);
            if (p == null)
                return false;

            // 验证: 8 秒内应出现带 python DLL 的新 _MEI 目录（说明解压成功）
            DateTime deadline = DateTime.Now.AddSeconds(8);
            while (DateTime.Now < deadline)
            {
                string found;
                if (HasFreshPythonDll(before, out found))
                {
                    Log("extraction ok: " + found);
                    return true;
                }
                if (p.HasExited)
                {
                    Log("launched process exited early (exit=" + p.ExitCode + ")");
                    return false;
                }
                Thread.Sleep(500);
            }
            Log("no fresh _MEI with python dll within 8s");
            return false;
        }
        catch (Exception e)
        {
            Log("launch error: " + e.Message);
            return false;
        }
    }

    static bool HasFreshPythonDll(HashSet<string> before, out string found)
    {
        found = null;
        try
        {
            foreach (string dir in Directory.GetDirectories(Path.GetTempPath(), "_MEI*"))
            {
                if (before.Contains(dir))
                    continue;
                if (Directory.GetFiles(dir, "python*.dll").Length > 0)
                {
                    found = dir;
                    return true;
                }
            }
        }
        catch { }
        return false;
    }
}
