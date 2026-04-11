"""
OpenCode Executor implementation.

OpenCode is an AI-powered coding agent with SDK and HTTP API support.
Documentation: https://opencode.ai/docs/zh-cn/sdk/
GitHub: https://github.com/opencode-ai/opencode
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import requests

from .base import BaseExecutor, ExecutionResult, ExecutionStatus, ExecutorConfig, logger


class OpenCodeSDKClient:
    """
    OpenCode HTTP API Client.
    
    Based on OpenCode SDK documentation:
    https://opencode.ai/docs/zh-cn/sdk/
    """
    
    def __init__(self, base_url: str, api_key: Optional[str] = None, timeout: int = 3600):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._headers = {"Content-Type": "application/json"}
        if api_key:
            self._headers["Authorization"] = f"Bearer {api_key}"
    
    def health(self) -> Dict[str, Any]:
        """Check server health status."""
        response = requests.get(
            f"{self.base_url}/health",
            headers=self._headers,
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    
    def create_session(self, project_id: Optional[str] = None) -> Dict[str, Any]:
        """Create a new session."""
        payload = {}
        if project_id:
            payload["project_id"] = project_id
        
        response = requests.post(
            f"{self.base_url}/session",
            headers=self._headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    
    def get_session(self, session_id: str) -> Dict[str, Any]:
        """Get session info."""
        response = requests.get(
            f"{self.base_url}/session/{session_id}",
            headers=self._headers,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all sessions."""
        response = requests.get(
            f"{self.base_url}/sessions",
            headers=self._headers,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    
    def prompt(
        self,
        session_id: str,
        parts: List[Dict[str, Any]],
        format: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Send a prompt to a session.
        
        Args:
            session_id: Session identifier
            parts: List of message parts (e.g., [{"type": "text", "text": "..."}])
            format: Optional structured output format (JSON Schema)
        
        Returns:
            Response with structured output if format specified
        """
        payload = {"parts": parts}
        if format:
            payload["format"] = format
        
        response = requests.post(
            f"{self.base_url}/session/{session_id}/prompt",
            headers=self._headers,
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()
    
    def cancel_session(self, session_id: str) -> Dict[str, Any]:
        """Cancel a running session."""
        response = requests.post(
            f"{self.base_url}/session/{session_id}/cancel",
            headers=self._headers,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    
    def list_projects(self) -> List[Dict[str, Any]]:
        """List all projects."""
        response = requests.get(
            f"{self.base_url}/projects",
            headers=self._headers,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    
    def create_project(self, path: str) -> Dict[str, Any]:
        """Create a new project."""
        response = requests.post(
            f"{self.base_url}/project",
            headers=self._headers,
            json={"path": path},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()


class OpenCodeExecutor(BaseExecutor):
    """
    OpenCode executor implementation with SDK support.
    
    OpenCode is an AI-powered coding agent that can:
    - Write and modify code
    - Run commands
    - Browse the web
    - Execute tasks autonomously
    
    Supports modes:
    - webui: Open browser for manual interaction
    - cli: Command line execution
    - api: HTTP API calls via SDK client
    - attach: Attach to running server
    """
    
    @property
    def name(self) -> str:
        return "OpenCode"
    
    @property
    def supported_modes(self) -> List[str]:
        return ["webui", "cli", "api", "attach"]
    
    def __init__(self, config: Optional[ExecutorConfig] = None):
        super().__init__(config)
        self._client: Optional[OpenCodeSDKClient] = None
    
    def _get_client(self) -> OpenCodeSDKClient:
        """Get or create SDK client."""
        if self._client is None:
            self._client = OpenCodeSDKClient(
                base_url=self.config.api_url or self.config.web_url or "http://localhost:4096",
                api_key=self.config.api_key,
                timeout=self.config.timeout,
            )
        return self._client
    
    def health_check(self) -> bool:
        """Check if OpenCode server is available."""
        try:
            client = self._get_client()
            health = client.health()
            return health.get("healthy", False)
        except Exception as e:
            logger.debug(f"OpenCode health check failed: {e}")
            return False
    
    def get_web_url(self, task_id: Optional[str] = None) -> Optional[str]:
        """Get OpenCode web UI URL."""
        return self.config.web_url or None
    
    def execute(self, instruction: str, task_id: str, dry_run: bool = False) -> ExecutionResult:
        """Execute instruction using OpenCode."""
        self._stats["total_executions"] += 1
        self._check_security(instruction)
        
        if dry_run:
            return ExecutionResult(
                task_id=task_id,
                success=True,
                status=ExecutionStatus.COMPLETED,
                stdout=f"[DRY RUN] Would execute via {self.name}: " + instruction[:100],
                duration=0.0,
            )
        
        logger.info(f"Executing via {self.name} for task {task_id}")
        
        if self.config.mode == "webui":
            return self._execute_webui(instruction, task_id)
        elif self.config.mode == "cli":
            return self._execute_cli(instruction, task_id)
        elif self.config.mode == "api":
            return self._execute_api(instruction, task_id)
        elif self.config.mode == "attach":
            return self._execute_attach(instruction, task_id)
        else:
            return ExecutionResult(
                task_id=task_id,
                success=False,
                status=ExecutionStatus.FAILED,
                error_message=f"Unsupported mode: {self.config.mode}",
            )
    
    def _execute_webui(self, instruction: str, task_id: str) -> ExecutionResult:
        """Execute via Web UI - opens browser for manual interaction."""
        result = ExecutionResult(
            task_id=task_id,
            success=False,
            status=ExecutionStatus.WAITING_INPUT,
        )
        
        web_url = self.config.web_url
        if not web_url:
            result.error_message = "Web UI URL not configured"
            result.status = ExecutionStatus.FAILED
            return result
        
        logger.info(f"Opening OpenCode Web UI: {web_url}")
        logger.info(f"Task instruction: {instruction}")
        
        webbrowser.open(web_url)
        
        result.metadata["web_url"] = web_url
        result.metadata["instruction"] = instruction
        result.metadata["message"] = "Please complete the task in the OpenCode Web UI"
        
        self._stats["successful"] += 1
        return result
    
    def _execute_cli(self, instruction: str, task_id: str) -> ExecutionResult:
        """Execute via OpenCode CLI."""
        start_time = time.time()
        
        result = ExecutionResult(
            task_id=task_id,
            success=False,
            status=ExecutionStatus.RUNNING,
        )
        
        self._current_execution = result
        
        work_dir = os.path.abspath(self.config.work_dir)
        os.makedirs(work_dir, exist_ok=True)
        
        try:
            cmd = [
                self.config.cli_path or "opencode",
                "run",
                "--task-id", task_id,
                "--work-dir", work_dir,
                instruction,
            ]
            
            logger.info(f"Running OpenCode CLI: {' '.join(cmd)}")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=work_dir,
            )
            
            try:
                stdout, stderr = process.communicate(timeout=self.config.timeout)
                
                result.stdout = stdout
                result.stderr = stderr
                result.exit_code = process.returncode
                result.success = process.returncode == 0
                result.status = ExecutionStatus.COMPLETED if result.success else ExecutionStatus.FAILED
                
                if result.success:
                    self._stats["successful"] += 1
                else:
                    self._stats["failed"] += 1
                
            except subprocess.TimeoutExpired:
                process.kill()
                result.status = ExecutionStatus.TIMEOUT
                result.error_message = f"Execution timed out after {self.config.timeout}s"
                self._stats["timeout"] += 1
                
        except FileNotFoundError:
            result.status = ExecutionStatus.FAILED
            result.error_message = f"OpenCode CLI not found: {self.config.cli_path}"
            self._stats["failed"] += 1
            
        except Exception as e:
            result.status = ExecutionStatus.FAILED
            result.error_message = str(e)
            self._stats["failed"] += 1
            
        finally:
            result.duration = time.time() - start_time
            self._current_execution = None
        
        return result
    
    def _execute_api(self, instruction: str, task_id: str) -> ExecutionResult:
        """Execute via OpenCode SDK using Node.js bridge in WSL."""
        start_time = time.time()
        
        result = ExecutionResult(
            task_id=task_id,
            success=False,
            status=ExecutionStatus.RUNNING,
        )
        
        self._current_execution = result
        
        try:
            work_dir = os.path.abspath(self.config.work_dir)
            os.makedirs(work_dir, exist_ok=True)
            
            bridge_script = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "scripts",
                "opencode_bridge.mjs"
            )
            
            if not os.path.exists(bridge_script):
                result.status = ExecutionStatus.FAILED
                result.error_message = f"OpenCode bridge script not found: {bridge_script}"
                self._stats["failed"] += 1
                return result
            
            wsl_work_dir = work_dir.replace("\\", "/").replace("D:", "/mnt/d").replace("C:", "/mnt/c")
            wsl_bridge_script = bridge_script.replace("\\", "/").replace("D:", "/mnt/d").replace("C:", "/mnt/c")
            
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            wsl_node_modules = os.path.join(project_root, "third_party", "nodejs", "node_modules")
            wsl_node_modules = wsl_node_modules.replace("\\", "/").replace("D:", "/mnt/d").replace("C:", "/mnt/c")
            
            cmd = [
                "wsl", "node",
                "--require", f"{wsl_node_modules}/@opencode-ai/sdk/dist/index.js",
                wsl_bridge_script,
                "--task", instruction,
                "--task-id", task_id,
                "--url", self.config.api_url or self.config.web_url or "http://localhost:4096",
                "--work-dir", wsl_work_dir,
                "--model-provider", self.config.model_provider or "opencode",
                "--model-id", self.config.model_id or "minimax-m2.5-free",
            ]
            
            env = os.environ.copy()
            env["NODE_PATH"] = wsl_node_modules
            
            logger.info(f"Running OpenCode SDK bridge via WSL: {' '.join(cmd)}")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )
            
            stdout, stderr = process.communicate(timeout=self.config.timeout)
            
            result.stdout = stdout
            result.stderr = stderr
            result.exit_code = process.returncode
            
            for line in stdout.strip().split('\n'):
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    if data.get('type') == 'result':
                        result.success = data.get('success', False)
                        result.status = ExecutionStatus.COMPLETED if result.success else ExecutionStatus.FAILED
                        result.stdout = data.get('summary', '')
                        result.files_created = data.get('files_created', [])
                        result.files_modified = data.get('files_modified', [])
                        if data.get('errors'):
                            result.stderr = '\n'.join(data.get('errors', []))
                        result.metadata['session_id'] = data.get('sessionId')
                        result.metadata['raw_output'] = data.get('raw_output')
                        break
                    elif data.get('type') == 'error':
                        result.status = ExecutionStatus.FAILED
                        result.error_message = data.get('message', 'Unknown error')
                except json.JSONDecodeError:
                    pass
            
            if result.status == ExecutionStatus.RUNNING:
                result.status = ExecutionStatus.FAILED if process.returncode != 0 else ExecutionStatus.COMPLETED
            
            if result.success:
                self._stats["successful"] += 1
            else:
                self._stats["failed"] += 1
                
        except subprocess.TimeoutExpired:
            process.kill()
            result.status = ExecutionStatus.TIMEOUT
            result.error_message = f"Execution timed out after {self.config.timeout}s"
            self._stats["timeout"] += 1
            
        except FileNotFoundError as e:
            result.status = ExecutionStatus.FAILED
            result.error_message = f"WSL or Node.js not found: {e}"
            self._stats["failed"] += 1
            
        except Exception as e:
            result.status = ExecutionStatus.FAILED
            result.error_message = str(e)
            self._stats["failed"] += 1
            
        finally:
            result.duration = time.time() - start_time
            self._current_execution = None
        
        return result
    
    def _execute_attach(self, instruction: str, task_id: str) -> ExecutionResult:
        """Execute by attaching to running OpenCode server via API."""
        return self._execute_api(instruction, task_id)
    
    def cancel(self, task_id: str) -> bool:
        """Cancel a running execution."""
        if self._current_execution and self._current_execution.task_id == task_id:
            session_id = self._current_execution.metadata.get("session_id")
            if session_id:
                try:
                    client = self._get_client()
                    client.cancel_session(session_id)
                    logger.info(f"Cancelled session {session_id}")
                except Exception as e:
                    logger.error(f"Failed to cancel session: {e}")
            
            self._current_execution.status = ExecutionStatus.CANCELLED
            self._stats["cancelled"] += 1
            return True
        return False
