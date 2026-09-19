#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import time
import threading
import paramiko
import subprocess
from datetime import datetime
from colorama import Fore,init
init(autoreset=True)

class ClusterGuardian:
    def __init__(self, config_path="config.json"):
        with open(config_path, "r") as f:
            self.config = json.load(f)
        self.my_ip = self.config["my_ip"]
        self.nodes = self.config["cluster_nodes"]
        self.leader = None
        self.is_leader = False
        self.running = True
        self.recovery_key_path = None
        for node in self.nodes:
            if node["ip"] == self.my_ip:
                self.recovery_key_path = node["recovery_key"]
                break
        if not self.recovery_key_path:
            print(f"{Fore.RED}[-] 未找到本机恢复密钥配置")
            sys.exit(1)
        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    def _load_private_key(self):
        return paramiko.RSAKey.from_private_key_file(self.recovery_key_path)

    def _ssh_connect(self, host, user="kali", timeout=5):
        try:
            self.ssh_client.connect(host, username=user, pkey=self._load_private_key(), timeout=timeout)
            return True
        except:
            return False

    def _ssh_exec(self, host, command):
        if not self._ssh_connect(host):
            return None
        try:
            stdin, stdout, stderr = self.ssh_client.exec_command(command)
            output = stdout.read().decode() + stderr.read().decode()
            self.ssh_client.close()
            return output
        except:
            return None

    def elect_leader(self):
        all_ips = sorted([node["ip"] for node in self.nodes])
        self.leader = all_ips[0]
        self.is_leader = (self.leader == self.my_ip)
        print(f"{Fore.GREEN}[*] 当前集群领导者: {self.leader}, 本机角色: {'Leader' if self.is_leader else 'Worker'}")

    def leader_loop(self):
        while self.running:
            if not self.is_leader:
                time.sleep(5)
                continue
            workers = [node["ip"] for node in self.nodes if node["ip"] != self.my_ip]
            targets = [node["ip"] for node in self.nodes if node["ip"] != self.my_ip]
            for i, worker in enumerate(workers):
                target = targets[i]
                self._assign_check_task(worker, target)
            time.sleep(self.config["check_interval"])

    def _assign_check_task(self, worker_ip, target_ip):
        cmd = f"python3 {os.path.abspath(__file__)} --check {target_ip}"
        threading.Thread(target=self._ssh_exec, args=(worker_ip, cmd)).start()

    def check_node(self, target_ip):
        print(f"{Fore.GREEN}[*] 正在检查节点 {target_ip} ...")
        anomalies = []
        passwd_content = self._ssh_exec(target_ip, "cat /etc/passwd")
        if passwd_content:
            for line in passwd_content.splitlines():
                if ":0:" in line and not line.startswith("root:"):
                    anomalies.append(f"未知UID 0账户: {line}")
        else:
            anomalies.append("无法获取 /etc/passwd")

        shadow_content = self._ssh_exec(target_ip, "cat /etc/shadow | grep root")
        if shadow_content and "!" in shadow_content.split(":")[1]:
            anomalies.append("root账户被锁定或密码被更改")

        auth_keys = self._ssh_exec(target_ip, "cat ~/.ssh/authorized_keys")
        if auth_keys and "cluster_recovery" not in auth_keys:
            anomalies.append("存在未知SSH公钥")

        ps_output = self._ssh_exec(target_ip, "ps aux | grep -E 'nc|bash -i|python -c|perl -e' | grep -v grep")
        if ps_output and ps_output.strip():
            anomalies.append(f"可疑进程: {ps_output.strip()}")

        if anomalies:
            print(f"{Fore.RED}[!] 节点 {target_ip} 可能已被攻陷！异常项: {anomalies}")
            self.recover_node(target_ip, anomalies)
        else:
            print(f"{Fore.GREEN}[+] 节点 {target_ip} 状态正常")

    def recover_node(self, target_ip, anomalies):
        print(f"[!!!] 开始恢复节点 {target_ip} ...")
        local_scripts_dir = self.config["recovery_scripts_dir"]
        remote_dir = "/tmp/recovery"
        self._ssh_exec(target_ip, f"mkdir -p {remote_dir}")
        for script in ["reset_root.sh", "clean_ssh.sh", "kill_malicious.sh"]:
            local_path = os.path.join(local_scripts_dir, script)
            subprocess.run(f"scp -i {self.recovery_key_path} {local_path} kali@{target_ip}:{remote_dir}/", shell=True)
        self._ssh_exec(target_ip, f"cd {remote_dir} && chmod +x *.sh && sudo ./reset_root.sh")
        self._ssh_exec(target_ip, f"cd {remote_dir} && sudo ./clean_ssh.sh")
        self._ssh_exec(target_ip, f"cd {remote_dir} && sudo ./kill_malicious.sh")
        with open("recovery.log", "a") as f:
            f.write(f"{datetime.now()} - 恢复节点 {target_ip}, 异常: {anomalies}\n")
        print(f"{Fore.GREEN}[+] 节点 {target_ip} 恢复操作已执行")

    def run(self):
        self.elect_leader()
        if self.is_leader:
            threading.Thread(target=self.leader_loop).start()
        while self.running:
            time.sleep(1)

if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--check":
        guardian = ClusterGuardian()
        guardian.check_node(sys.argv[2])
    else:
        guardian = ClusterGuardian()
        try:
            guardian.run()
        except KeyboardInterrupt:
            guardian.running = False
            print(f"{Fore.GREEN}[*] 守护进程退出")
