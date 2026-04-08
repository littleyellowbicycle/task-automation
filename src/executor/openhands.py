"""
OpenHands Executor implementation.

OpenHands is an AI-driven software development agent.
GitHub: https://github.com/All-Hands-AI/OpenHands
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import requests

from .base import BaseExecutor, ExecutionResult, ExecutionStatus, ExecutorConfig


class OpenHandsExecutor(BaseExecutor):
    """
    OpenHands executor implementation.
    
    OpenHands is an AI-driven software development agent that can:
    - Write and modify code
    - Run commands
    - Browse the web
    - Call APIs
    
    GitHub: https://github.com/All-Hands-AI/OpenHands
    """
    
    @property
    def name(self) -> str:
        return "OpenHands"
    
    @property
    def supported_modes(self) -> List[str]:
        return ["webui", "cli", "api"]
    
    def health_check(self) -> bool:
        """Check if OpenHands is available."""
        if self.config.mode == "webui":
            if self.config.web_url:
                try:
                    resp = requests.get(f"{self.config.web_url}", timeout=5)
                    return resp.status_code == 200
                except:
                    return False
        elif self.config.mode == "cli":
            try:
                result = subprocess.run(
                    [self.config.cli_path or "openhands", "--version"],
                    capture_output=True,
                    timeout=10,
                )
                return result.returncode == 0
            except:
                return False
        elif self.config.mode == "api":
            if self.config.api_url:
                try:
                    resp = requests.get(f"{self.config.api_url}/health", timeout=5)
                    return resp.status_code == 200
                except:
                    return False
        return False
    
    def get_web_url(self, task_id: Optional[str] = None) -> Optional[str]:
        """Get OpenHands web UI URL."""
        return self.config.web_url or None
    
    def execute(self, instruction: str, task_id: str, dry_run: bool = False) -> ExecutionResult:
        """Execute instruction using OpenHands."""
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
        
        logger.info(f"Opening OpenHands Web UI: {web_url}")
        logger.info(f"Task instruction: {instruction}")
        
        webbrowser.open(web_url)
        
        result.metadata["web_url"] = web_url
        result.metadata["instruction"] = instruction
        result.metadata["message"] = "Please complete the task in the OpenHands Web UI"
        
        self._stats["successful"] += 1
        return result
    
    def _execute_cli(self, instruction: str, task_id: str) -> ExecutionResult:
        """Execute via OpenHands CLI."""
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
                self.config.cli_path or "openhands",
                "run",
                "--task", task_id,
                "--work-dir", work_dir,
                instruction,
            ]
            
            logger.info(f"Running OpenHands CLI: {' '.join(cmd)}")
            
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
            result.error_message = f"OpenHands CLI not found: {self.config.cli_path}"
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
        """Execute via OpenHands API."""
        start_time = time.time()
        
        result = ExecutionResult(
            task_id=task_id,
            success=False,
            status=ExecutionStatus.RUNNING,
        )
        
        if not self.config.api_url:
            result.error_message = "API URL not configured"
            result.status = ExecutionStatus.FAILED
            return result
        
        try:
            headers = {
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            }
            
            payload = {
                "instruction": instruction,
                "task_id": task_id,
                "work_dir": self.config.work_dir,
            }
            
            logger.info(f"Calling OpenHands API: {self.config.api_url}")
            
            response = requests.post(
                f"{self.config.api_url}/api/conversations",
                headers=headers,
                json=payload,
                timeout=self.config.timeout,
            )
            
            if response.status_code == 200:
                data = response.json()
                conversation_id = data.get("conversation_id") or data.get("id")
                
                result.metadata["conversation_id"] = conversation_id
                result.metadata["api_response"] = data
                
                start_poll = time.time()
                poll_interval = 5
                max_polls = int(self.config.timeout / poll_interval)
                
                for i in range(max_polls):
                    poll_response = requests.get(
                        f"{self.config.api_url}/api/conversations/{conversation_id}",
                        headers=headers,
                        timeout=10,
                    )
                    
                    if poll_response.status_code == 200:
                        poll_data = poll_response.json()
                        status = poll_data.get("status")
                        
                        if status == "completed":
                            result.success = True
                            result.status = ExecutionStatus.COMPLETED
                            result.stdout = json.dumps(poll_data.get("result", {}), indent=2)
                            self._stats["successful"] += 1
                            break
                        elif status == "failed":
                            result.status = ExecutionStatus.FAILED
                            result.error_message = poll_data.get("error", "Unknown error")
                            self._stats["failed"] += 1
                            break
                        
                        time.sleep(poll_interval)
                else:
                    result.status = ExecutionStatus.TIMEOUT
                    result.error_message = "API polling timed out"
                    self._stats["timeout"] += 1
            else:
                result.status = ExecutionStatus.FAILED
                result.error_message = f"API returned {response.status_code}: {response.text[:200]}"
                self._stats["failed"] += 1
                
        except requests.exceptions.RequestException as e:
            result.status = ExecutionStatus.FAILED
            result.error_message = f"API request failed: {e}"
            self._stats["failed"] += 1
            
        except Exception as e:
            result.status = ExecutionStatus.FAILED
            result.error_message = str(e)
            self._stats["failed"] += 1
            
        finally:
            result.duration = time.time() - start_time
        
        return result
