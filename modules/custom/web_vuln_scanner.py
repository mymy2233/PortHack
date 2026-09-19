import os,sys
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
lib_path = os.path.join(project_root, "lib")
sys.path.insert(0, lib_path)
import json
import tempfile
import threading
import time
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scanner import DetailedVulnerabilityScanner
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
        self.name = "Web Vulnerability"
        self.port = None
        self.protocol = "http"
        self.url = None
        self.platform = "multi"
        self.use_msf = False

    def exploit(self, target_ip=None, target_port=None, lhost=None, url=None, session=None):
        """执行 Web 漏洞扫描，返回发现的漏洞列表和可利用信息"""
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect((target_ip, target_port or 80))
            request = b"HEAD / HTTP/1.0\r\n\r\n"
            sock.send(request)
            resp = sock.recv(1024).decode(errors='ignore')
            sock.close()
            if "MiniShare" in resp:
                safe_print(f"{Fore.GREEN}[*] 检测到 MiniShare 服务，尝试精确缓冲区溢出...")
                from modules.custom.precise_minishare_overflow import Module as MiniShareModule
                ms_mod = MiniShareModule()
                return ms_mod.exploit(target_ip, target_port or 80, lhost)
        except Exception as e:
            safe_print(f"{Fore.RED}[-] MiniShare 检测失败: {e}")
        if target_port == 443:
            if url == None:
                target_url = f"https://{target_ip}"
        else:
            if url == None:
                target_url = f"http://{target_ip}"
                if target_port and target_port != 80:
                    target_url += f":{target_port}"

        print(f"{Fore.GREEN}[*] 启动 Web 漏洞扫描: {target_url}")
        scanner = DetailedVulnerabilityScanner(target_url)
        scanner.scan_exposed_files_comprehensive()
        scanner.scan_common_vulnerabilities()
        scanner.scan_ports()
        scanner.check_ssl_tls()

        # 提取关键发现
        critical_vulns = [v for v in scanner.vulnerabilities if v['level'] in ['CRITICAL', 'HIGH']]
        exposed_configs = [f for f in scanner.exposed_files if any(ext in f['path'].lower() for ext in ['.env', '.config', '.sql', '.bak'])]
        # 保存扫描报告到临时文件，供后续分析
        report_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
        report_file = f"{report_file}/web_scan_{target_ip}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        scanner.save_detailed_report(report_file)
        if critical_vulns:
            return True, f"{Fore.GREEN}发现 {len(critical_vulns)} 个高危漏洞，详情见 {report_file}"
        elif exposed_configs:
            return True, f"{Fore.GREEN}发现 {len(exposed_configs)} 个敏感配置文件，详情见 {report_file}"
        else:
            return False, "未发现可直接利用的高危漏洞"
