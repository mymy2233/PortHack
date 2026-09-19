import os
import sys
import platform
import subprocess
import signal

if sys.platform == "win32":
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.GetStdHandle(-11)
    mode = ctypes.c_ulong()
    kernel32.GetConsoleMode(handle, ctypes.byref(mode))
    mode.value |= 0x0004
    kernel32.SetConsoleMode(handle, mode)

signal.signal(signal.SIGINT, lambda sig, frame: (print("\033[31m[!] Error\033[0m"), os._exit(0)))

def get_distro_id():
    if platform.system() != "Linux":
        return None
    try:
        with open("/etc/os-release", "r") as f:
            for line in f:
                if line.startswith("ID="):
                    return line.strip().split("=")[1].strip('"').lower()
    except FileNotFoundError:
        return "unknown"

def init_rely():
    lib = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib')
    hlib = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'modules/custom/lib')
    hydra = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'modules/custom/main')
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rely')
    err = False
    arch_proc = subprocess.run(['dpkg', '--print-architecture'], capture_output=True, text=True)
    if arch_proc.returncode != 0:
        arch_proc = subprocess.run(['uname', '-m'], capture_output=True, text=True)
        if arch_proc.returncode != 0:
            print("无法获取系统架构")
            sys.exit(1)
        if arch_proc == 'x86_64':
            arch = x86_64
        elif arch_proc == 'aarch64':
            arch = 'arm64'
        else:
            print("无法获取系统架构")
            sys.exit(1)
    else:
        arch = arch_proc.stdout.strip()
    try:
        result = subprocess.run(['msfconsole', '--version'], capture_output=True, text=True, timeout=10)
        #result = subprocess.run(['man'], capture_output=True, text=True, timeout=10)
        #上面的是测试，如果要看整体把第二行的注释去掉
        a = (result.returncode != 0) or (not os.path.isdir(lib)) or (not os.path.isdir(hlib)) or (not os.path.isfile(hydra))
        if a:
            if result.returncode != 0:
                err = True
            if not os.path.isdir(lib):
                print("lib不存在，正在修复...")
                libxf = subprocess.run(['unzip', '-o', 'rely/pyrely.zip'], capture_output=True, text=True, timeout=10)
                if libxf.returncode != 0:
                    print("无法解压，请检查 unzip 是否可用")
                    sys.exit(1)
                else:
                   zip = 'lib.'+arch+'.zip'
                   libxf = subprocess.run(['unzip', zip], capture_output=True, text=True, timeout=10)
                   if libxf.returncode != 0:
                       print("错误：未找到合适的Python3库依赖压缩包")
                   else:
                       libxf = subprocess.run(['mv', zip.strip('.zip'), 'lib'], capture_output=True, text=True, timeout=10)
                       if libxf.returncode != 0:
                           print("错误：重命名失败")
                       else:
                           libxf = subprocess.run(['rm', 'lib.amd64.zip', 'lib.arm64.zip'], capture_output=True, text=True, timeout=10)
                           if libxf.returncode != 0:
                               print("错误：压缩包删除失败")
                           else:
                               print("lib修复成功")
            if ((not os.path.isdir(hlib)) or (not os.path.isfile(hydra))):
                print("hydra不存在，正在修复...")
                hydar_arch = path+'/hydra_'+arch
                hydraxf = subprocess.run(['cp', hydar_arch, 'modules/custom/'], capture_output=True, text=True, timeout=10)
                if hydraxf.returncode != 0:
                    print(f"错误：不存在当前系统架构的hydra")
                else:
                    hydraxf = subprocess.run(['mv', 'modules/custom/hydra_'+arch, 'modules/custom/main'], capture_output=True, text=True, timeout=10)
                    if hydraxf.returncode != 0:
                        print(f"错误：hydra命名失败，hydra模块将无法使用")
                if not os.path.isdir(hlib):
                    lib_arch = 'rely/lib_'+arch
                    hydraxf = subprocess.run(['cp', lib_arch, 'modules/custom/'], capture_output=True, text=True, timeout=10)
                    if hydraxf.returncode != 0:
                        print(f"错误：不存在当前系统架构的hydra依赖")
        else:
            print("依赖正常")
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        print(f"错误：{e}")
        err = True
    if err:
        distro = get_distro_id()
        #print(distro)
        if distro == "ubuntu":
            suffix = "ubuntu"
        elif distro == 'kali':
            suffix = 'kali'
        elif distro in ("debian", "parrot"):
            suffix = "debian"
        else:
            suffix = "linux"

        if install.returncode != 0:
            MII = input("MSF未安装，是否尝试安装？[N/y]")
            if (MII == 'Y') or (MII == 'y'):
                subprocess.run(['apt', 'install', 'metasploit-framework', '-y'])
            else:
                pass
    sys.exit(1)
