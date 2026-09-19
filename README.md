这是我的第一个开源项目，一个自动渗透工具
灵感主要来源于Hacknet里的PortHack，后来突发奇想就开发了这个项目

你下载好之后只要解压就能运行，不需要什么可恨的第三方库和依赖
安装Python环境？不存在的
安装依赖？不存在的！
甚至在安卓上也能运行！仅仅只是在安卓上无法使用密码爆破模块而已
只是唯一的缺点就是暂时只支持Linux平台，因为文件路径和二进制的太难搞了
所以你如果非要在Windows上运行也不是不行，只是有些模块是不支持的，所以会报错

首先进入工作目录，然后运行
```python
python3 PortHack.py init
```

并且要把config.json.tmp和nodes.json.tmp改成config.json和nodes.json
并更改里面的cluster_nodes、recovery_scripts_dir、nodes和wordlist_local的内容
因为本工具依赖这些内容，否则无法正常工作
比如项目在/root下，那么/root/porthack就是项目路径
如果你将本项目分发出去，修改节点列表还可以实现集群攻击
cluster_daemon.py和deploy_cluster.sh就是用来实现集群攻击的，保护节点不被攻陷

至于Python的第三方库并不是使用系统的，所以如果第三方库无法使用或要更新库需要运行
```bash
./pyrely_update.sh
```

那怎么自定义模块呢？
只要把这些代码放到modules/custom里就行
```python
import os,sys
lib_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "lib")
sys.path.insert(0, lib_path) #要用第三方库就要加这个
from colorama import Fore,init
init(autoreset=True)
import fcntl
def safe_print(msg):
    with open(sys.stdout.fileno(), 'wb', closefd=False) as fd:
        fcntl.flock(fd, fcntl.LOCK_EX)  # 加锁
        sys.stdout.write(msg + '\\n')
        sys.stdout.flush()
        fcntl.flock(fd, fcntl.LOCK_UN)  # 解锁
        #别问我为什么不用内置print，问就是终端看起来像坨屎

class Module:
    def __init__(self):
        self.name = "这里写模块名称"
        self.port = 这里写模块攻击的端口，不加引号的
        #self.session = True  #写提权模块的时候取消注释，只能写False或True
        self.protocol = "这里写连接协议，比如tcp"
        self.platform = "这里写作用于哪一个平台的，这个只在是提权模块的时候才适用"
        self.use_msf = 这里写是否使用msf，一样只能写False或True
        #self.url = None #要使用url的时候加这个，并且要把所有的target_ip改成url

    def exploit(self, target_ip=None, target_port=80, lhost=None):
        pass #这里写你的攻击或提权代码
```

本项目致力于在最小化环境中也能成功运行

如果喜欢就点个star吧
