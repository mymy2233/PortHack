修复了一大堆bug，优化了一下结构

这次的部署需要把config.json和nodes.json改成更改里面的cluster_nodes、recovery_scripts_dir、hydra_path、nodes和wordlist_local的内容
因为本工具依赖这些内容，否则无法正常工作
比如项目在/root下，那么/root/porthack就是项目根目录
如果你将本项目分发出去，修改节点列表还可以实现集群攻击
cluster_daemon.py和deploy_cluster.sh就是用来实现集群攻击的，保护节点不被攻陷

由于Python的第三方库并不是使用系统的，所以如果第三方库无法使用或要更新库需要运行
```bash
./pyrely_update.sh
```
其它内容请看old/README.md

本项目致力于在最小化环境中也能成功运行
如果喜欢就点个star吧
