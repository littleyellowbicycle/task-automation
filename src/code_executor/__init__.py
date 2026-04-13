import asyncio
import json
import os
import platform
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..utils import get_logger
from ..exceptions import SecurityViolationError

logger = get_logger("code_executor")

SDK_SCRIPT = str(Path(__file__).resolve().parent.parent.parent / "third_party" / "nodejs" / "opencode-sdk.mjs")
SDK_NODE_DIR = str(Path(__file__).resolve().parent.parent.parent / "third_party" / "nodejs")
SDK_MODULES_DIR = os.path.join(SDK_NODE_DIR, "node_modules")


@dataclass
class ExecutionResult:
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    duration: float
    is_timeout: bool = False
    repo_url: Optional[str] = None
    files_created: List[str] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)
    session_id: Optional[str] = None


class CodeExecutor:
    def __init__(
        self,
        api_url: str = "http://localhost:4096",
        work_dir: str = "./workspace",
        timeout: int = 600,
        model_provider: str = "opencode",
        model_id: str = "minimax-m2.5-free",
        allowed_commands: Optional[List[str]] = None,
        forbidden_paths: Optional[List[str]] = None,
        host: str = "",
        port: int = 0,
    ):
        self.api_url = api_url.rstrip("/")
        self.work_dir = work_dir
        self.timeout = timeout
        self.model_provider = model_provider
        self.model_id = model_id
        self.allowed_commands = allowed_commands or ["create", "modify", "read"]
        self.forbidden_paths = forbidden_paths or ["/etc", "/root", "/sys", "/proc"]
        self._ensure_workdir()
        self._ensure_sdk_deps()

    def _ensure_workdir(self):
        Path(self.work_dir).mkdir(parents=True, exist_ok=True)

    def _ensure_sdk_deps(self):
        if os.path.isdir(os.path.join(SDK_MODULES_DIR, "@opencode-ai")):
            return

        node_exe = self._find_node()
        if node_exe == "node":
            try:
                subprocess.run(
                    ["node", "--version"],
                    capture_output=True,
                    timeout=5,
                )
            except (FileNotFoundError, subprocess.TimeoutExpired):
                logger.warning("Node.js not found, skipping SDK installation")
                return

        logger.info("OpenCode SDK dependencies not found, installing...")
        try:
            npm_cmd = self._find_npm()
            result = subprocess.run(
                [npm_cmd, "install"],
                cwd=SDK_NODE_DIR,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                logger.info("OpenCode SDK dependencies installed successfully")
            else:
                logger.warning(f"SDK installation warning: {result.stderr[:200]}")
        except FileNotFoundError:
            logger.warning("npm not found, cannot install SDK dependencies automatically")
        except subprocess.TimeoutExpired:
            logger.warning("SDK installation timed out")
        except Exception as e:
            logger.warning(f"SDK installation failed: {e}")

    @staticmethod
    def _find_node() -> str:
        node_exe = shutil.which("node")
        if node_exe:
            return node_exe
        is_windows = platform.system() == "Windows"
        if is_windows:
            candidates = [
                r"C:\Program Files\nodejs\node.exe",
                r"C:\Program Files (x86)\nodejs\node.exe",
            ]
        else:
            candidates = [
                "/usr/bin/node",
                "/usr/local/bin/node",
                os.path.expanduser("~/.nvm/versions/node/current/bin/node"),
                os.path.expanduser("~/.local/bin/node"),
                "/snap/bin/node",
            ]
        for candidate in candidates:
            if os.path.isfile(candidate):
                return candidate
        return "node"

    @staticmethod
    def _find_npm() -> str:
        npm_exe = shutil.which("npm")
        if npm_exe:
            return npm_exe
        is_windows = platform.system() == "Windows"
        if is_windows:
            candidates = [
                r"C:\Program Files\nodejs\npm.cmd",
                r"C:\Program Files (x86)\nodejs\npm.cmd",
            ]
        else:
            candidates = [
                "/usr/bin/npm",
                "/usr/local/bin/npm",
                os.path.expanduser("~/.nvm/versions/node/current/bin/npm"),
                os.path.expanduser("~/.local/bin/npm"),
                "/snap/bin/npm",
            ]
        for candidate in candidates:
            if os.path.isfile(candidate):
                return candidate
        return "npm"

    def _check_security(self, instruction: str) -> bool:
        instruction_lower = instruction.lower()
        for forbidden in self.forbidden_paths:
            if forbidden in instruction_lower:
                raise SecurityViolationError(f"Instruction contains forbidden path: {forbidden}")
        return True

    def _build_env(self) -> Dict[str, str]:
        env = os.environ.copy()
        env["OPENCODE_API_URL"] = self.api_url
        return env

    async def _run_sdk(self, *args: str, timeout: Optional[int] = None) -> Dict[str, Any]:
        node_exe = self._find_node()
        cmd = [node_exe, SDK_SCRIPT, *args]
        env = self._build_env()
        effective_timeout = timeout or self.timeout

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=effective_timeout
            )
            stdout = stdout_bytes.decode("utf-8", errors="replace").strip()
            stderr = stderr_bytes.decode("utf-8", errors="replace").strip()

            if proc.returncode != 0:
                if stdout:
                    try:
                        err_data = json.loads(stdout)
                        error_msg = err_data.get("error", stdout)
                    except json.JSONDecodeError:
                        error_msg = stdout or stderr
                else:
                    error_msg = stderr or f"Process exited with code {proc.returncode}"
                logger.error(f"SDK error: {error_msg}")
                return {"error": error_msg}

            if not stdout:
                return {"error": "Empty response from SDK"}

            return json.loads(stdout)

        except asyncio.TimeoutError:
            if proc and proc.returncode is None:
                proc.kill()
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse SDK output: {e}")
            return {"error": f"Invalid JSON from SDK: {stdout[:200]}"}
        except FileNotFoundError:
            logger.error("Node.js not found. Install Node.js to use OpenCode SDK.")
            return {"error": "Node.js not found"}
        except Exception as e:
            logger.error(f"SDK execution failed: {e}")
            return {"error": str(e)}

    async def _health_check(self) -> bool:
        try:
            result = await self._run_sdk("health", timeout=10)
            return result.get("healthy", False)
        except Exception as e:
            logger.warning(f"OpenCode health check failed: {e}")
            return False

    def _diagnose_connection(self) -> str:
        from urllib.parse import urlparse

        parsed = urlparse(self.api_url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 4096

        lines = [
            "",
            "=" * 60,
            "OpenCode 服务连接失败诊断",
            "=" * 60,
            f"  配置地址: {self.api_url}",
            f"  目标主机: {host}",
            f"  目标端口: {port}",
        ]

        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((host, port))
            sock.close()
            if result == 0:
                lines.append("  端口状态: 开放 (端口可达，但服务未响应健康检查)")
            else:
                lines.append(f"  端口状态: 关闭 (无法连接到 {host}:{port})")
        except socket.gaierror:
            lines.append(f"  DNS 解析: 失败 (无法解析主机名: {host})")
        except Exception as e:
            lines.append(f"  连接测试: {e}")

        lines.extend([
            "",
            "  可能的原因:",
            "    1. OpenCode 服务未启动 - 请先启动 OpenCode 服务",
            "    2. 地址配置错误 - 请检查 OPENCODE_API_URL 环境变量",
            f"    3. 网络不通 - 请确认 {host}:{port} 可达",
            "",
            "  启动 OpenCode 服务示例:",
            f"    opencode server --host 0.0.0.0 --port {port}",
            "",
            "  或在 .env 中修改配置:",
            f"    OPENCODE_API_URL=http://<opencode-host>:{port}",
            "=" * 60,
        ])

        return "\n".join(lines)

    async def _try_start_opencode(self) -> bool:
        opencode_exe = shutil.which("opencode")
        if not opencode_exe:
            is_windows = platform.system() == "Windows"
            if is_windows:
                candidates = [
                    r"C:\Users\{}\AppData\Local\opencode\opencode.exe".format(os.getenv("USERNAME", "")),
                    r"C:\Program Files\opencode\opencode.exe",
                ]
            else:
                candidates = [
                    os.path.expanduser("~/.local/bin/opencode"),
                    "/usr/local/bin/opencode",
                    "/usr/bin/opencode",
                ]
            for candidate in candidates:
                if os.path.isfile(candidate):
                    opencode_exe = candidate
                    break

        if not opencode_exe:
            logger.info("OpenCode CLI not found, cannot auto-start service")
            return False

        from urllib.parse import urlparse
        parsed = urlparse(self.api_url)
        host = parsed.hostname or "0.0.0.0"
        port = str(parsed.port or 4096)

        logger.info(f"Attempting to start OpenCode service at {host}:{port}...")

        try:
            cmd = [opencode_exe, "server", "--host", host, "--port", port]
            if platform.system() == "Windows":
                proc = subprocess.Popen(
                    cmd,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )

            for _ in range(30):
                await asyncio.sleep(1)
                if await self._health_check():
                    logger.info(f"OpenCode service started successfully (PID: {proc.pid})")
                    return True

            logger.warning("OpenCode service did not become healthy within 30s")
            return False
        except Exception as e:
            logger.warning(f"Failed to start OpenCode service: {e}")
            return False

    async def _create_session(self, title: str = "") -> Optional[str]:
        try:
            result = await self._run_sdk("create-session", title or "Task Automation", timeout=15)
            if "error" in result:
                logger.error(f"Failed to create session: {result['error']}")
                return None
            session_id = result.get("id")
            if session_id:
                logger.info(f"Created OpenCode session: {session_id}")
            return session_id
        except Exception as e:
            logger.error(f"Failed to create OpenCode session: {e}")
            return None

    async def _send_message(self, session_id: str, instruction: str) -> Optional[Dict[str, Any]]:
        try:
            args = ["prompt", session_id, instruction]
            if self.model_provider and self.model_id:
                args.extend([self.model_provider, self.model_id])

            result = await self._run_sdk(*args, timeout=self.timeout)

            if "error" in result:
                logger.error(f"Prompt failed: {result['error']}")
                return None

            return result
        except asyncio.TimeoutError:
            logger.error(f"Prompt timed out after {self.timeout}s")
            return None
        except Exception as e:
            logger.error(f"Prompt request failed: {e}")
            return None

    async def _abort_session(self, session_id: str) -> None:
        try:
            await self._run_sdk("abort", session_id, timeout=10)
        except Exception:
            pass

    async def execute(self, instruction: str, dry_run: bool = False) -> ExecutionResult:
        start_time = time.time()

        if dry_run:
            logger.info(f"[DRY RUN] Would execute: {instruction}")
            return ExecutionResult(
                success=True,
                exit_code=0,
                stdout=f"[DRY RUN] {instruction}",
                stderr="",
                duration=0,
            )

        self._check_security(instruction)

        logger.info(f"Executing OpenCode: {instruction[:80]}...")

        healthy = await self._health_check()
        if not healthy:
            logger.warning("OpenCode server not healthy, attempting to start...")
            started = await self._try_start_opencode()
            if started:
                healthy = True
            else:
                logger.error(self._diagnose_connection())
                return ExecutionResult(
                    success=False,
                    exit_code=-1,
                    stdout="",
                    stderr=f"OpenCode service unavailable at {self.api_url}. "
                           f"Please start the service or check OPENCODE_API_URL configuration.",
                    duration=time.time() - start_time,
                )

        session_id = await self._create_session(title=instruction[:50])
        if not session_id:
            duration = time.time() - start_time
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr="Failed to create OpenCode session",
                duration=duration,
            )

        try:
            result = await asyncio.wait_for(
                self._send_message(session_id, instruction),
                timeout=self.timeout,
            )

            duration = time.time() - start_time

            if result is None:
                await self._abort_session(session_id)
                return ExecutionResult(
                    success=False,
                    exit_code=-1,
                    stdout="",
                    stderr="OpenCode execution failed or timed out",
                    duration=duration,
                    is_timeout=True,
                    session_id=session_id,
                )

            stdout_parts = []
            for part in result.get("parts", []):
                part_type = part.get("type", "")
                if part_type == "text":
                    stdout_parts.append(part.get("text", ""))
                elif part_type == "tool-invocation":
                    tool_inv = part.get("toolInvocation", {})
                    tool_name = tool_inv.get("toolName", "")
                    args = tool_inv.get("args", {})
                    if tool_name in ("write", "edit", "create"):
                        file_path = args.get("path", args.get("file_path", ""))
                        if file_path:
                            stdout_parts.append(f"[File: {file_path}]")

            assistant_text = "\n".join(stdout_parts)

            info = result.get("info", {})
            finish = info.get("finish", "stop")
            success = finish == "stop"

            if not success:
                assistant_text += f"\n[Finish: {finish}]"

            if info.get("error"):
                success = False
                assistant_text += f"\n[Error: {info['error']}]"

            if success:
                logger.info(f"OpenCode execution successful ({duration:.1f}s)")
            else:
                logger.warning(f"OpenCode execution completed with issues ({duration:.1f}s)")

            return ExecutionResult(
                success=success,
                exit_code=0 if success else 1,
                stdout=assistant_text,
                stderr="",
                duration=duration,
                repo_url=self.extract_repo_url(assistant_text),
                session_id=session_id,
            )

        except asyncio.TimeoutError:
            duration = time.time() - start_time
            logger.error(f"OpenCode execution timed out after {self.timeout}s")
            await self._abort_session(session_id)
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=f"Execution timed out after {self.timeout} seconds",
                duration=duration,
                is_timeout=True,
                session_id=session_id,
            )
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"OpenCode execution error: {e}")
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration=duration,
                session_id=session_id,
            )

    def extract_repo_url(self, output: str) -> Optional[str]:
        patterns = [
            r'https?://github\.com/[^\s]+',
            r'https?://gitlab\.com/[^\s]+',
            r'file:///[^\s]+',
        ]
        for pattern in patterns:
            match = re.search(pattern, output)
            if match:
                return match.group()
        return None
