#!/bin/bash

# ====== 请根据实际情况修改以下变量 ======
SCAPY_NODES=()
HPING_NODES=("192.168.1.102")   # 你的攻击节点
ALL_NODES=("${SCAPY_NODES[@]}" "${HPING_NODES[@]}")
USER="kali"
PASSWORD="kali"                     # 节点机 SSH 密码
# 私钥在主控机上的路径（根据你的实际位置修改）
PRIVATE_KEY_PATH="/root/.ssh/cluster_recovery"
# =====================================

# 生成 config.json 模板（用于后续替换 my_ip）
cat > /tmp/config_template.json << 'EOF'
{
    "lhost": "192.168.1.103",
    "lport": 4444,
    "msf_rpc_host": "127.0.0.1",
    "msf_rpc_port": 55553,
    "msf_rpc_pass": "kali",
    "cluster_nodes": [
        {"ip": "192.168.1.102", "user": "kali", "recovery_key": "/home/kali/.ssh/cluster_recovery"}
    ],
    "leader_election_port": 5000,
    "check_interval": 30,
    "recovery_scripts_dir": "/home/kali/pwnkit/recovery"
}
EOF

for node in "${ALL_NODES[@]}"; do
    echo "[*] 部署到 $node"

    # 判断节点角色（目前只有 hping3 模板）
    TEMPLATE_TYPE=""
    if [[ " ${SCAPY_NODES[@]} " =~ " ${node} " ]]; then
        TEMPLATE_TYPE="scapy_template"
    else
        TEMPLATE_TYPE="hping3_template"
    fi

    # 生成带 my_ip 的 config.json
    cp /tmp/config_template.json /tmp/config_$node.json
    sed -i "s/\"cluster_nodes\"/\"my_ip\": \"$node\",\\n    \"cluster_nodes\"/" /tmp/config_$node.json

    # 创建远程目录
    sshpass -p "$PASSWORD" ssh $USER@$node "mkdir -p ~/pwnkit/recovery"

    # ---------- 新增：上传私钥 ----------
    if [ -f "$PRIVATE_KEY_PATH" ]; then
        echo "[*] 上传私钥到 $node"
        sshpass -p "$PASSWORD" scp "$PRIVATE_KEY_PATH" $USER@$node:/home/$USER/.ssh/cluster_recovery
        sshpass -p "$PASSWORD" ssh $USER@$node "chmod 600 /home/$USER/.ssh/cluster_recovery"
    else
        echo "[-] 警告：私钥文件 $PRIVATE_KEY_PATH 不存在，跳过上传"
    fi
    # -----------------------------------

    # 上传守护进程和配置
    sshpass -p "$PASSWORD" scp cluster_daemon.py /tmp/config_$node.json $USER@$node:~/pwnkit/
    sshpass -p "$PASSWORD" ssh $USER@$node "mv ~/pwnkit/config_$node.json ~/pwnkit/config.json"

    # 上传对应恢复模板
    sshpass -p "$PASSWORD" scp -r recovery/${TEMPLATE_TYPE}/* $USER@$node:~/pwnkit/recovery/
    sshpass -p "$PASSWORD" ssh $USER@$node "chmod +x ~/pwnkit/recovery/*.sh"

    # 启动守护进程
    sshpass -p "$PASSWORD" ssh $USER@$node "cd ~/pwnkit && nohup python3 cluster_daemon.py > daemon.log 2>&1 &"

    echo "[+] $node 部署完成 (角色: ${TEMPLATE_TYPE})"
done

# 清理临时文件
rm -f /tmp/config_template.json /tmp/config_*.json
