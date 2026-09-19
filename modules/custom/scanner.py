#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
import socket
import ssl
import re
import time
import os,sys
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
lib_path = os.path.join(project_root, "lib")
sys.path.insert(0, lib_path)
from datetime import datetime
from urllib.parse import urlparse, urljoin, quote
import threading
import concurrent.futures
import json
from colorama import Fore, Style, init
import html
import tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fcntl
def safe_print(msg):
    with open(sys.stdout.fileno(), 'wb', closefd=False) as fd:
        fcntl.flock(fd, fcntl.LOCK_EX)  # 加锁
        sys.stdout.write(msg + '\n')
        sys.stdout.flush()
        fcntl.flock(fd, fcntl.LOCK_UN)  # 解锁

init(autoreset=True)

class Module:
    def __init__(self):
        self.name = "File Exposure Scanner"
        self.port = None
        self.protocol = "http"
        self.platform = "multi"
        self.use_msf = False

    def exploit(self, target_ip=None, target_port=None, lhost=None, session=None):
        pass

class DetailedVulnerabilityScanner:
    """带有精确文件泄露信息的详细漏洞扫描器"""
    
    def __init__(self, target_url):
        self.target_url = self._normalize_url(target_url)
        self.parsed_url = urlparse(self.target_url)
        self.hostname = self.parsed_url.hostname
        self.base_url = f"{self.parsed_url.scheme}://{self.parsed_url.netloc}"
        self.vulnerabilities = []
        self.exposed_files = []
        self.sensitive_data = []
        self.open_ports = []
        
        # 设置会话
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })
        self.session.verify = False
        requests.packages.urllib3.disable_warnings()
        self.max_workers = 20
        self.timeout = 3
        self.session.timeout = self.timeout
    
    def _normalize_url(self, url):
        """规范化URL"""
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        return url.rstrip('/')
    
    def _log_vulnerability(self, level, category, title, description, details=None):
        """记录漏洞发现（带详细信息）"""
        vuln = {
            'level': level,  # 严重、高危、中危、低危、信息
            'category': category,
            'title': title,
            'description': description,
            'details': details or {},
            'timestamp': datetime.now().isoformat()
        }
        self.vulnerabilities.append(vuln)

        if level in ('CRITICAL', 'HIGH'):
            colors = {
                'CRITICAL': Fore.RED,
                'HIGH': Fore.MAGENTA,
                'MEDIUM': Fore.YELLOW,
                'LOW': Fore.CYAN,
                'INFO': Fore.GREEN
            }
            color = colors.get(level, Fore.WHITE)
            safe_print(f"{color}[{level}] {category}: {title}")
            if description:
                safe_print(f"     描述: {description}")
            if details:
                for key, value in details.items():
                    safe_print(f"     {key}: {value}")
            safe_print()
    
        return vuln
    
    def _log_exposed_file(self, file_path, status_code, content_length, content_sample=None, file_type=None):
        """记录暴露的文件（带详细信息）"""
        exposed_file = {
            'path': file_path,
            'full_url': urljoin(self.base_url, file_path),
            'status_code': status_code,
            'content_length': content_length,
            'file_type': file_type or self._detect_file_type(file_path),
            'content_sample': content_sample[:500] if content_sample else None,  # 限制样本大小
            'timestamp': datetime.now().isoformat()
        }
        self.exposed_files.append(exposed_file)
        
        safe_print(f"{Fore.YELLOW}[暴露文件] {file_path}")
        safe_print(f"     地址: {exposed_file['full_url']}")
        safe_print(f"     状态: {status_code}, 大小: {content_length} 字节")
        safe_print(f"     类型: {exposed_file['file_type']}")
        if content_sample:
            sample = content_sample[:200]
            safe_print(f"     样本: {self._escape_content(sample)}")
        safe_print()
        
        return exposed_file
    
    def _log_sensitive_data(self, data_type, content, context=None):
        """记录发现的敏感数据"""
        sensitive = {
            'type': data_type,
            'content': content,
            'context': context or {},
            'timestamp': datetime.now().isoformat()
        }
        self.sensitive_data.append(sensitive)
        
        safe_print(f"{Fore.RED}[敏感数据] {data_type}: {content}")
        if context:
            safe_print(f"     上下文: {context}")
        safe_print()
        
        return sensitive
    
    def _detect_file_type(self, file_path):
        """根据扩展名检测文件类型"""
        ext = os.path.splitext(file_path)[1].lower()
        
        file_types = {
            '.php': 'PHP脚本',
            '.js': 'JavaScript',
            '.json': 'JSON数据',
            '.txt': '文本文件',
            '.log': '日志文件',
            '.sql': 'SQL数据库',
            '.zip': '压缩包',
            '.tar': '压缩包',
            '.gz': '压缩包',
            '.yml': 'YAML配置',
            '.yaml': 'YAML配置',
            '.xml': 'XML文件',
            '.html': 'HTML页面',
            '.htm': 'HTML页面',
            '.config': '配置文件',
            '.env': '环境配置',
            '.git': 'Git仓库',
            '.bak': '备份文件',
            '.old': '旧版本文件',
            '.tmp': '临时文件',
            '.swp': '交换文件'
        }
        
        return file_types.get(ext, '未知')
    
    def _escape_content(self, content):
        """转义内容以便安全显示"""
        try:
            return html.escape(str(content))
        except:
            return str(content)[:200]
    
    # ==================== 扫描方法 ====================
    
    def scan_exposed_files_comprehensive(self):
        """全面扫描暴露的文件"""
        # 分类文件列表
        file_categories = {
            '配置文件': [
                '/.env', '/.env.example', '/.env.local', '/.env.production', '/.env.development',
                '/config.php', '/configuration.php', '/settings.php', '/config.json', '/config.yaml',
                '/config.yml', '/settings.json', '/web.config', '/appsettings.json',
                '/application/config/config.php', '/application/config/database.php',
                '/includes/config.php', '/inc/config.php', '/system/config.php',
                '/config/database.yml', '/config/database.yaml', '/config/database.json',
                '/config/credentials.json', '/config/secrets.yml', '/config/application.yml'
            ],
            
            '备份文件': [
                '/backup.zip', '/backup.tar', '/backup.tar.gz', '/backup.sql', '/backup.bak',
                '/dump.sql', '/database.sql', '/db.sql', '/data.sql', '/mysql.sql',
                '/backup/database.sql', '/sql/backup.sql', '/db/backup.sql',
                '/site.bak', '/website.bak', '/app.bak', '/config.bak',
                '/backup.old', '/database.old', '/config.old',
                '/www.zip', '/site.tar.gz', '/project_backup.zip',
                '/admin/backup.sql', '/admin/db_backup.sql'
            ],
            
            'Git文件': [
                '/.git/config', '/.git/HEAD', '/.git/index', '/.git/description',
                '/.git/hooks/', '/.git/info/exclude', '/.git/logs/HEAD',
                '/.git/objects/', '/.git/refs/heads/', '/.git/refs/tags/',
                '/.git/COMMIT_EDITMSG', '/.git/FETCH_HEAD', '/.git/ORIG_HEAD'
            ],
            
            '版本控制': [
                '/.svn/entries', '/.svn/wc.db', '/.svn/format',
                '/.hg/store/00manifest.i', '/.hg/dirstate', '/.hg/branch',
                '/.bzr/branch-format', '/.bzr/branch/branch.conf'
            ],
            
            '日志文件': [
                '/logs/access.log', '/logs/error.log', '/logs/app.log',
                '/log/access.log', '/log/error.log', '/log/app.log',
                '/var/log/access.log', '/var/log/error.log', '/var/log/app.log',
                '/tmp/access.log', '/tmp/error.log',
                '/access.log', '/error.log', '/app.log',
                '/debug.log', '/system.log', '/security.log',
                '/apache/access.log', '/apache/error.log',
                '/nginx/access.log', '/nginx/error.log'
            ],
            
            '管理面板': [
                '/admin/', '/admin/index.php', '/admin/login.php', '/admin/admin.php',
                '/administrator/', '/administrator/index.php',
                '/wp-admin/', '/wp-admin/index.php',
                '/wp-login.php', '/login.php', '/admin/login',
                '/cpanel/', '/webmin/', '/plesk/',
                '/manager/', '/system/', '/controlpanel/',
                '/backend/', '/backoffice/', '/dashboard/',
                '/user/', '/users/', '/account/', '/accounts/'
            ],
            
            '数据库文件': [
                '/phpmyadmin/', '/mysql/', '/pma/', '/dbadmin/',
                '/adminer.php', '/adminer/', '/db/',
                '/database/', '/sql/', '/sqlite/', '/sqlite3/'
            ],
            
            '开发文件': [
                '/phpinfo.php', '/test.php', '/info.php', '/debug.php',
                '/.gitignore', '/composer.json', '/package.json', '/package-lock.json',
                '/yarn.lock', '/pom.xml', '/build.xml', '/gradle.properties',
                '/requirements.txt', '/Pipfile', '/Pipfile.lock',
                '/docker-compose.yml', '/docker-compose.yaml', '/dockerfile',
                '/.dockerignore', '/.env.docker', '/docker.env',
                '/.travis.yml', '/.circleci/config.yml', '/.github/workflows/',
                '/README.md', '/CHANGELOG.md', '/LICENSE', '/CONTRIBUTING.md'
            ],
            
            '敏感端点': [
                '/robots.txt', '/sitemap.xml', '/sitemap_index.xml',
                '/crossdomain.xml', '/clientaccesspolicy.xml',
                '/.well-known/security.txt', '/security.txt',
                '/.well-known/apple-app-site-association',
                '/.well-known/assetlinks.json',
                '/humans.txt', '/ads.txt', '/.htaccess', '.htpasswd',
                '/server-status', '/server-info', '/php-fpm-status'
            ],
            
            '备份目录': [
                '/backups/', '/backup/', '/old/', '/archive/',
                '/temp/', '/tmp/', '/cache/', '/uploads/',
                '/downloads/', '/export/', '/import/'
            ]
        }
        
        all_paths = []
        for category, file_list in file_categories.items():
            for file_path in file_list:
                all_paths.append((file_path, category))
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = {executor.submit(self._check_single_file, path, cat): (path, cat) 
                       for path, cat in all_paths}
    
            for future in concurrent.futures.as_completed(futures):
                pass

        self._scan_common_directories()
    
    def _check_single_file(self, file_path, category):
        """检查单个文件或目录"""
        full_url = urljoin(self.base_url, file_path)
        
        try:
            response = self.session.get(full_url, timeout=5, allow_redirects=False)
            
            if response.status_code == 200:
                content_length = len(response.content)
                
                # 判断是目录还是文件
                is_directory = file_path.endswith('/') or response.headers.get('Content-Type', '').startswith('text/html')
                
                if is_directory:
                    self._log_vulnerability(
                        '中危' if '管理面板' in category else '低危',
                        '目录暴露',
                        f'暴露的目录: {file_path}',
                        f'该目录可公开访问',
                        {
                            'url': full_url,
                            '状态码': response.status_code,
                            '内容类型': response.headers.get('Content-Type', ''),
                            '内容长度': content_length,
                            '类别': category
                        }
                    )
                else:
                    # 分析文件内容
                    content_sample = None
                    if content_length < 10000:  # 只分析小文件
                        try:
                            content_sample = response.text if response.text else str(response.content[:500])
                        except:
                            content_sample = str(response.content[:500])
                    
                    file_info = self._log_exposed_file(
                        file_path, 
                        response.status_code, 
                        content_length, 
                        content_sample,
                        self._detect_file_type(file_path)
                    )
                    
                    # 检查文件中是否包含敏感数据
                    if content_sample:
                        self._analyze_file_content(content_sample, file_path)
            
            elif response.status_code in [301, 302, 307, 308]:
                self._log_vulnerability(
                    '信息',
                    '重定向发现',
                    f'存在重定向: {file_path}',
                    f'重定向至: {response.headers.get("Location", "未知")}',
                    {
                        'url': full_url,
                        '重定向目标': response.headers.get('Location', ''),
                        '类别': category
                    }
                )
            
            elif response.status_code == 403:
                self._log_vulnerability(
                    '信息',
                    '访问被拒绝',
                    f'访问被拒绝: {file_path}',
                    '文件存在但访问被禁止',
                    {
                        'url': full_url,
                        '类别': category
                    }
                )
            
        except requests.exceptions.Timeout:
            pass  # 静默跳过超时
        except Exception as e:
            pass  # 静默跳过其他错误
    
    def _scan_common_directories(self):
        """扫描常见目录"""
        common_dirs = [
            '/api/', '/api/v1/', '/api/v2/', '/graphql', '/graphiql',
            '/swagger/', '/swagger-ui/', '/redoc/', '/docs/', '/documentation/',
            '/static/', '/assets/', '/media/', '/images/', '/img/', '/css/', '/js/',
            '/vendor/', '/lib/', '/library/', '/includes/', '/inc/',
            '/src/', '/source/', '/app/', '/application/', '/system/',
            '/modules/', '/plugins/', '/themes/', '/templates/', '/views/',
            '/configs/', '/settings/', '/data/', '/database/', '/db/',
            '/export/', '/import/', '/upload/', '/download/', '/files/',
            '/private/', '/secret/', '/hidden/', '/secure/', '/protected/'
        ]
        
        for directory in common_dirs:
            self._check_single_file(directory, '常见目录')
    
    def _analyze_file_content(self, content, file_path):
        """分析文件内容中的敏感数据"""
        
        # 检查数据库凭据
        db_patterns = [
            (r'(?i)mysql_connect\s*\([^)]+\)', 'MySQL连接'),
            (r'(?i)DB_HOST\s*=\s*[\'"]([^\'"]+)[\'"]', '数据库主机'),
            (r'(?i)DB_USER\s*=\s*[\'"]([^\'"]+)[\'"]', '数据库用户'),
            (r'(?i)DB_PASS\s*=\s*[\'"]([^\'"]+)[\'"]', '数据库密码'),
            (r'(?i)DB_NAME\s*=\s*[\'"]([^\'"]+)[\'"]', '数据库名'),
            (r'(?i)database_url\s*[:=]\s*[\'"]([^\'"]+)[\'"]', '数据库URL'),
            (r'(?i)mongodb://[^\s\'"]+', 'MongoDB URL'),
            (r'(?i)postgresql://[^\s\'"]+', 'PostgreSQL URL'),
            (r'(?i)redis://[^\s\'"]+', 'Redis URL')
        ]
        
        for pattern, label in db_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                self._log_sensitive_data(
                    f'数据库凭据 (位于 {os.path.basename(file_path)})',
                    str(match),
                    {'文件': file_path, '类型': label}
                )
        
        # 检查API密钥
        api_key_patterns = [
            (r'AKIA[0-9A-Z]{16}', 'AWS访问密钥'),
            (r'AIza[0-9A-Za-z\-_]{35}', 'Google API密钥'),
            (r'sk_live_[0-9a-zA-Z]{24}', 'Stripe密钥(生产)'),
            (r'rk_live_[0-9a-zA-Z]{24}', 'Stripe受限密钥'),
            (r'sk_test_[0-9a-zA-Z]{24}', 'Stripe测试密钥'),
            (r'EAACEdEose0cBA[0-9A-Za-z]+', 'Facebook访问令牌'),
            (r'ghp_[0-9a-zA-Z]{36}', 'GitHub令牌'),
            (r'gho_[0-9a-zA-Z]{36}', 'GitHub令牌'),
            (r'github_pat_[0-9a-zA-Z]{22}_[0-9a-zA-Z]{59}', 'GitHub精细令牌'),
            (r'xox[baprs]-[0-9a-zA-Z]{10,48}', 'Slack令牌'),
            (r'sk-[0-9a-zA-Z]{48}', 'OpenAI API密钥'),
            (r'tg[0-9]+:[0-9a-zA-Z\-_]+', 'Telegram机器人令牌'),
            (r'[0-9a-f]{32}', 'MD5哈希(可能是API密钥)'),
            (r'[0-9a-f]{40}', 'SHA-1哈希(可能是API密钥)'),
            (r'[0-9a-f]{64}', 'SHA-256哈希(可能是API密钥)')
        ]
        
        for pattern, label in api_key_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                # 跳过看起来像十六进制颜色或其他常见十六进制字符串的内容
                if len(match) == 6 and re.match(r'^[0-9a-f]{6}$', match, re.IGNORECASE):
                    continue
                if len(match) == 32 and 'access_token' not in content.lower():
                    continue
                
                self._log_sensitive_data(
                    f'API密钥 (位于 {os.path.basename(file_path)})',
                    f'{label}: {match[:10]}...',
                    {'文件': file_path, '类型': label, '完整密钥': match}
                )
        
        # 检查邮箱
        emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', content)
        for email in set(emails[:5]):  # 限制5个唯一邮箱
            self._log_sensitive_data(
                f'邮箱地址 (位于 {os.path.basename(file_path)})',
                email,
                {'文件': file_path}
            )
        
        # 检查内网IP
        internal_ips = re.findall(r'\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2[0-9]|3[0-1])\.\d{1,3}\.\d{1,3})\b', content)
        for ip in set(internal_ips[:3]):  # 限制3个唯一IP
            self._log_sensitive_data(
                f'内网IP (位于 {os.path.basename(file_path)})',
                ip,
                {'文件': file_path}
            )
        
        # 检查配置文件中的密码
        if any(ext in file_path.lower() for ext in ['.env', '.config', '.php', '.yml', '.yaml', '.json']):
            password_matches = re.findall(r'(?i)(?:password|passwd|pwd|secret|token|key)\s*[:=]\s*[\'"]([^\'"]+)[\'"]', content)
            for password in password_matches[:3]:  # 限制3个
                if len(password) > 3 and not password.lower() in ['null', 'none', '""', "''"]:
                    self._log_sensitive_data(
                        f'密码/密钥 (位于 {os.path.basename(file_path)})',
                        f'{password[:5]}...' if len(password) > 8 else '***',
                        {'文件': file_path, '上下文': '配置文件'}
                    )
    
    def scan_common_vulnerabilities(self):
        """扫描常见Web漏洞"""
        # SQL注入测试
        self.test_sql_injection()
        
        # XSS测试
        self.test_xss()
        
        # 目录遍历测试
        self.test_directory_traversal()
        
        # 命令注入测试
        self.test_command_injection()
        
        # 检查调试端点
        self.check_debug_endpoints()
    
    def test_sql_injection(self):
        """测试SQL注入漏洞"""
        test_params = ['id', 'page', 'user', 'category', 'search', 'product', 'article']
        payloads = [
            "'",
            "' OR '1'='1",
            "' AND 1=1--",
            "1' AND '1'='1",
            "1' OR '1'='1'--",
            "' UNION SELECT NULL--",
            "' UNION SELECT 1,2,3--",
            "admin'--",
            "1' AND SLEEP(5)--"
        ]
        
        sql_errors = [
            "sql syntax", "mysql_fetch", "ora-", "microsoft ole db",
            "postgresql", "sqlite", "warning:", "mysql_query",
            "unclosed quotation", "syntax error", "SQLSTATE",
            "mysql error", "pg_query", "sqlserver"
        ]
        for param in test_params:
            for payload in payloads:
                try:
                    test_url = f"{self.target_url}/?{param}={quote(payload)}"
                    response = self.session.get(test_url, timeout=5)
                    
                    # 检查SQL错误
                    for error in sql_errors:
                        if error in response.text.lower():
                            self._log_vulnerability(
                                '严重',
                                'SQL注入',
                                f'通过参数 {param} 发现SQL注入',
                                f'载荷: {payload} 触发了SQL错误',
                                {
                                    '参数': param,
                                    '载荷': payload,
                                    'URL': test_url,
                                    '错误指示器': error,
                                    '响应码': response.status_code
                                }
                            )
                            return True
                    
                    # 检查响应时间差异（用于盲注）
                    if 'SLEEP' in payload.upper():
                        # 可以在此处测量响应时间
                        pass
                    
                except Exception:
                    continue
        
        return False
    
    def test_xss(self):
        """测试XSS漏洞"""
        test_params = ['q', 'search', 'keyword', 'name', 'message', 'comment', 'title']
        payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert(1)>",
            "\"><script>alert(1)</script>",
            "'><script>alert(1)</script>",
            "<svg/onload=alert(1)>",
            "javascript:alert(1)",
            "<iframe src=javascript:alert(1)>"
        ]
        
        for param in test_params:
            for payload in payloads:
                try:
                    test_url = f"{self.target_url}/?{param}={quote(payload)}"
                    response = self.session.get(test_url, timeout=5)
                    
                    # 检查载荷是否未编码地出现在响应中
                    if payload in response.text:
                        self._log_vulnerability(
                            '高危',
                            '跨站脚本攻击(XSS)',
                            f'通过参数 {param} 发现反射型XSS',
                            f'载荷未经编码被反射',
                            {
                                '参数': param,
                                '载荷': payload,
                                'URL': test_url,
                                '响应码': response.status_code
                            }
                        )
                        return True
                    
                except Exception:
                    continue
        
        return False
    
    def test_directory_traversal(self):
        """测试目录遍历漏洞"""
        test_params = ['file', 'path', 'page', 'load', 'document', 'template']
        payloads = [
            "../../../../etc/passwd",
            "..\\..\\..\\..\\windows\\system32\\drivers\\etc\\hosts",
            "../../../../etc/shadow",
            "../../../../windows/win.ini",
            "../../../../boot.ini"
        ]
        
        indicators = [
            "root:", "daemon:", "bin:", "sys:", "adm:",
            "[extensions]", "[mci extensions]", "for 16-bit app support"
        ]
        
        for param in test_params:
            for payload in payloads:
                try:
                    test_url = f"{self.target_url}/?{param}={quote(payload)}"
                    response = self.session.get(test_url, timeout=5)
                    
                    # 检查文件内容指示器
                    for indicator in indicators:
                        if indicator in response.text:
                            self._log_vulnerability(
                                '高危',
                                '目录遍历',
                                f'通过参数 {param} 发现目录遍历',
                                f'能够读取: {payload}',
                                {
                                    '参数': param,
                                    '载荷': payload,
                                    'URL': test_url,
                                    '发现指示器': indicator,
                                    '响应码': response.status_code,
                                    '响应样本': response.text[:200]
                                }
                            )
                            return True
                    
                except Exception:
                    continue
        
        return False
    
    def test_command_injection(self):
        """测试命令注入漏洞"""
        test_params = ['cmd', 'command', 'exec', 'execute', 'system', 'shell']
        payloads = [
            "; whoami",
            "| whoami",
            "&& whoami",
            "`whoami`",
            "$(whoami)",
            "; id",
            "| id",
            "&& id"
        ]
        
        for param in test_params:
            for payload in payloads:
                try:
                    test_url = f"{self.target_url}/?{param}=test{quote(payload)}"
                    response = self.session.get(test_url, timeout=5)
                    
                    # 检查命令输出
                    if any(user in response.text.lower() for user in ['www-data', 'root', 'administrator', 'user', 'uid=']):
                        self._log_vulnerability(
                            '严重',
                            '命令注入',
                            f'通过参数 {param} 发现命令注入',
                            f'载荷: {payload}',
                            {
                                '参数': param,
                                '载荷': payload,
                                'URL': test_url,
                                '响应码': response.status_code,
                                '响应样本': response.text[:200]
                            }
                        )
                        return True
                    
                except Exception:
                    continue
        
        return False
    
    def check_debug_endpoints(self):
        """检查调试和开发端点"""
        debug_endpoints = [
            '/debug', '/debug.php', '/debug.asp', '/debug.aspx',
            '/test', '/test.php', '/testing', '/testpage',
            '/phpinfo', '/phpinfo.php', '/info.php',
            '/status', '/server-status', '/server-info',
            '/console', '/admin/debug', '/system/debug',
            '/_debug', '/_debugbar', '/_profiler',
            '/web-console', '/rails/info', '/actuator',
            '/heapdump', '/threaddump', '/dump',
            '/trace', '/metrics', '/health', '/ping'
        ]
        
        
        for endpoint in debug_endpoints:
            full_url = urljoin(self.base_url, endpoint)
            
            try:
                response = self.session.get(full_url, timeout=5)
                
                if response.status_code == 200:
                    # 检查调试指示器
                    debug_indicators = [
                        'phpinfo', 'php version', 'debug', 'xdebug',
                        'environment', 'configuration', 'loaded modules',
                        'system information', 'server variables',
                        'thread dump', 'heap dump', 'actuator',
                        'metrics endpoint', 'health check'
                    ]
                    
                    content_lower = response.text.lower()
                    
                    for indicator in debug_indicators:
                        if indicator in content_lower:
                            self._log_vulnerability(
                                '中危',
                                '调试端点暴露',
                                f'调试端点暴露: {endpoint}',
                                f'包含调试信息: {indicator}',
                                {
                                    'URL': full_url,
                                    '指示器': indicator,
                                    '响应码': response.status_code,
                                    '内容长度': len(response.content)
                                }
                            )
                            break
                
            except Exception:
                continue
    
    def scan_ports(self):
        """扫描开放端口"""
        if not self.hostname:
            return
        
        
        common_ports = [
            (21, 'FTP'),
            (22, 'SSH'),
            (23, 'Telnet'),
            (25, 'SMTP'),
            (53, 'DNS'),
            (80, 'HTTP'),
            (110, 'POP3'),
            (143, 'IMAP'),
            (443, 'HTTPS'),
            (445, 'SMB'),
            (3306, 'MySQL'),
            (3389, 'RDP'),
            (5432, 'PostgreSQL'),
            (5900, 'VNC'),
            (6379, 'Redis'),
            (8080, 'HTTP代理'),
            (8443, 'HTTPS备用'),
            (27017, 'MongoDB')
        ]
        
        for port, service in common_ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex((self.hostname, port))
                
                if result == 0:
                    self.open_ports.append((port, service))
                    self._log_vulnerability(
                        '信息',
                        '开放端口',
                        f'端口 {port} ({service}) 开放',
                        f'{service} 服务可访问',
                        {
                            '端口': port,
                            '服务': service,
                            '主机': self.hostname
                        }
                    )
                
                sock.close()
                
            except Exception:
                pass
    
    def check_ssl_tls(self):
        """检查SSL/TLS配置"""
        if self.parsed_url.scheme != 'https':
            return
        
        
        try:
            context = ssl.create_default_context()
            
            with socket.create_connection((self.hostname, 443), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=self.hostname) as ssock:
                    tls_version = ssock.version()
                    cipher = ssock.cipher()
                    cert = ssock.getpeercert()
                    
                    issues = []
                    
                    # 检查TLS版本
                    if tls_version in ["TLSv1", "TLSv1.1"]:
                        issues.append(f"不安全的TLS版本: {tls_version}")
                    
                    # 检查密码套件
                    if cipher:
                        cipher_name = cipher[0]
                        weak_ciphers = ["RC4", "DES", "3DES", "MD5", "NULL", "EXP", "ANON"]
                        for weak in weak_ciphers:
                            if weak in cipher_name.upper():
                                issues.append(f"弱密码套件: {cipher_name}")
                                break
                    
                    # 检查证书
                    if cert:
                        expiry_date = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
                        now = datetime.now()
                        
                        if expiry_date < now:
                            issues.append("证书已过期")
                        elif (expiry_date - now).days < 30:
                            issues.append(f"证书将在 {(expiry_date - now).days} 天后过期")
                        
                        # 检查是否自签名
                        subject = dict(x[0] for x in cert['subject'])
                        issuer = dict(x[0] for x in cert['issuer'])
                        if subject == issuer:
                            issues.append("自签名证书")
                    
                    if issues:
                        self._log_vulnerability(
                            '中危',
                            'SSL/TLS问题',
                            f'TLS/SSL配置问题',
                            ', '.join(issues),
                            {
                                'tls版本': tls_version,
                                '密码套件': cipher[0] if cipher else '未知',
                                '问题': issues
                            }
                        )
                    
        except Exception as e:
            self._log_vulnerability(
                '信息',
                'SSL/TLS检查失败',
                f'无法检查SSL/TLS: {str(e)}',
                '',
                {'错误': str(e)}
            )
    
    def run_comprehensive_scan(self):
        """运行全面漏洞扫描"""
        start_time = time.time()
        
        # 运行所有扫描
        self.scan_exposed_files_comprehensive()
        self.scan_common_vulnerabilities()
        self.scan_ports()
        self.check_ssl_tls()
        
        end_time = time.time()
        
        
        self.display_summary()
    
    def display_summary(self):
        """显示扫描摘要"""
        # 按级别统计漏洞
        levels = {}
        for vuln in self.vulnerabilities:
            level = vuln['level']
            levels[level] = levels.get(level, 0) + 1
        
        safe_print(f"{Fore.CYAN}发现的漏洞:")
        for level in ['严重', '高危', '中危', '低危', '信息']:
            count = levels.get(level, 0)
            if count > 0:
                color = {
                    '严重': Fore.RED,
                    '高危': Fore.MAGENTA,
                    '中危': Fore.YELLOW,
                    '低危': Fore.CYAN,
                    '信息': Fore.GREEN
                }.get(level, Fore.WHITE)
                safe_print(f"  {color}{level}: {count}")
        
        
    def save_detailed_report(self, filename=os.path.dirname(os.path.abspath(__file__))):
        """保存详细报告为JSON文件"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"详细扫描报告_{timestamp}.json"
        
        report = {
            '扫描信息': {
                '目标': self.target_url,
                '主机名': self.hostname,
                '扫描时间': datetime.now().isoformat(),
                '扫描耗时': None
            },
            '摘要': {
                '漏洞总数': len(self.vulnerabilities),
                '暴露文件': len(self.exposed_files),
                '敏感数据': len(self.sensitive_data),
                '开放端口': len(self.open_ports)
            },
            '漏洞列表': self.vulnerabilities,
            '暴露文件列表': self.exposed_files,
            '敏感数据列表': self.sensitive_data,
            '开放端口列表': self.open_ports
        }
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            safe_print(f"{Fore.GREEN}[+] 报告保存至: {filename}")
            return filename
            
        except Exception as e:
            safe_print(f"{Fore.RED}[!] 保存失败: {e}")
            return None
    
    def save_text_report(self, filename=None):
        """保存文本格式报告"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"扫描报告_{timestamp}.txt"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("="*60 + "\n")
                f.write("           详细漏洞扫描报告\n")
                f.write("="*60 + "\n\n")
                f.write(f"目标: {self.target_url}\n")
                f.write(f"主机名: {self.hostname}\n")
                f.write(f"扫描时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("\n" + "="*60 + "\n\n")
                
                # 漏洞列表
                f.write("发现的漏洞:\n")
                f.write("-" * 40 + "\n\n")
                
                for vuln in self.vulnerabilities:
                    f.write(f"[{vuln['level']}] {vuln['category']}: {vuln['title']}\n")
                    f.write(f"     描述: {vuln['description']}\n")
                    if vuln.get('details'):
                        for key, value in vuln['details'].items():
                            f.write(f"     {key}: {value}\n")
                    f.write("\n")
                
                # 暴露文件
                f.write("\n暴露的文件:\n")
                f.write("-" * 40 + "\n\n")
                
                for file_info in self.exposed_files:
                    f.write(f"文件: {file_info['path']}\n")
                    f.write(f"     地址: {file_info['full_url']}\n")
                    f.write(f"     状态: {file_info['status_code']}, 大小: {file_info['content_length']} 字节\n")
                    f.write(f"     类型: {file_info['file_type']}\n")
                    if file_info.get('content_sample'):
                        f.write(f"     样本: {file_info['content_sample'][:200]}\n")
                    f.write("\n")
                
                # 敏感数据
                if self.sensitive_data:
                    f.write("\n发现的敏感数据:\n")
                    f.write("-" * 40 + "\n\n")
                    
                    for data in self.sensitive_data:
                        f.write(f"类型: {data['type']}\n")
                        f.write(f"     数据: {data['content']}\n")
                        if data.get('context'):
                            f.write(f"     上下文: {data['context']}\n")
                        f.write("\n")
                
                if self.open_ports:
                    f.write("\n开放的端口:\n")
                    f.write("-" * 40 + "\n\n")
                    
                    for port, service in self.open_ports:
                        f.write(f"端口 {port}: {service}\n")
                
                f.write("\n" + "="*60 + "\n")
                f.write("报告由详细漏洞扫描器生成\n")
                f.write("="*60 + "\n")
            
            safe_print(f"{Fore.GREEN}[+] 文件保存至: {filename}")
            return filename
            
        except Exception as e:
            safe_print(f"{Fore.RED}[!] 保存失败: {e}")
            return None

def main():
    """主函数"""
    import sys
    if len(sys.argv) > 1:
        target = sys.argv[1]
    else:
        target = input(f"{Fore.WHITE}请输入URL: ").strip()
    
    if not target:
        safe_print(f"{Fore.RED}[!] 无效的URL")
        return
    
    scanner = DetailedVulnerabilityScanner(target)
    
    scanner.run_comprehensive_scan()
    
    save = input(f"\n{Fore.WHITE}是否保存报告? (y/n): ").strip().lower()
    if save == 'y':
        json_file = scanner.save_detailed_report()
        txt_file = scanner.save_text_report()
        
        if json_file and txt_file:
            safe_print(f"{Fore.GREEN}[+] 报告文件:")
            safe_print(f"{Fore.GREEN}[+]   JSON: {json_file}")
            safe_print(f"{Fore.GREEN}[+]   文本: {txt_file}")

if __name__ == "__main__":
    main()
