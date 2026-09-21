using System.Runtime.InteropServices;

namespace Godswar.LootTool;

internal static class Program
{
    [STAThread]
    private static int Main(string[] args)
    {
        // Applied for both paths so a launcher script can point the tool at
        // another database or client, self test included.
        LootToolSettings.ApplyOverrides(
            ReadOption(args, "--connection-string"),
            ReadOption(args, "--client-root"));

        if (args.Any(static arg =>
                arg.Equals("--selftest", StringComparison.OrdinalIgnoreCase)))
        {
            // A WinExe has no console of its own; borrow the parent's so the
            // report is visible when the tool is launched from a terminal.
            AttachConsole(-1);
            return SelfTest.RunAsync().GetAwaiter().GetResult();
        }

        if (args.Any(static arg =>
                arg.Equals("--help", StringComparison.OrdinalIgnoreCase) ||
                arg.Equals("-h", StringComparison.OrdinalIgnoreCase)))
        {
            AttachConsole(-1);
            Console.WriteLine("Godswar 掉落表编辑工具");
            Console.WriteLine("  （无参数）                              打开图形界面");
            Console.WriteLine("  --selftest                              只跑数据层自测，不开窗口");
            Console.WriteLine("  --connection-string \"Host=...;Database=...\"  覆盖数据库连接串并记住");
            Console.WriteLine("  --client-root \"D:\\Godswar Origin\"        覆盖客户端目录并记住");
            return 0;
        }

        ApplicationConfiguration.Initialize();
        Application.Run(new MainForm());
        return 0;
    }

    private static string? ReadOption(string[] args, string name)
    {
        for (var index = 0; index < args.Length - 1; index++)
        {
            if (args[index].Equals(name, StringComparison.OrdinalIgnoreCase))
            {
                return args[index + 1];
            }
        }

        return null;
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool AttachConsole(int processId);
}
