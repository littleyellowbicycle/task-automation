"""Feishu (Lark) API client for bitable operations."""

import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any
import lark_oapi as lark
from lark_oapi.api.bitable.v1 import CreateAppTableRecordRequest, GetAppTableRecordRequest, UpdateAppTableRecordRequest

from .models import TaskRecord, TaskStatus
from ..utils import get_logger
from ..exceptions import FeishuAuthError, FeishuAPIError, FeishuRecordNotFoundError

logger = get_logger("feishu_client")


class FeishuClient:
    """
    Feishu (Lark) bitable client for task recording.
    
    Handles OAuth2 authentication and CRUD operations for task records.
    """
    
    def __init__(
        self,
        app_id: str = "",
        app_secret: str = "",
        table_id: str = "",
        token_refresh_buffer: int = 300,
    ):
        """
        Initialize Feishu client.
        
        Args:
            app_id: Feishu app ID
            app_secret: Feishu app secret
            table_id: Bitable table ID
            token_refresh_buffer: Seconds before expiry to refresh token
        """
        self.app_id = app_id or ""
        self.app_secret = app_secret or ""
        self.table_id = table_id or ""
        self.token_refresh_buffer = token_refresh_buffer
        
        # Lark SDK client
        self._client: Optional[lark.Client] = None
        self._tenant_access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
    
    def _get_client(self) -> lark.Client:
        """Get or create the Lark SDK client."""
        if self._client is None:
            self._client = lark.Client.builder()\
                .app_id(self.app_id)\
                .app_secret(self.app_secret)\
                .build()
        return self._client
    
    async def _get_tenant_access_token(self) -> str:
        """Get or refresh the tenant access token."""
        now = datetime.now()
        
        # Check if token needs refresh
        if self._tenant_access_token and self._token_expires_at:
            if now < self._token_expires_at:
                return self._tenant_access_token
        
        try:
            client = self._get_client()
            # Use the SDK's token management
            response = client.request(
                "POST",
                "/open-apis/auth/v3/tenant_access_token/internal",
                body={"app_id": self.app_id, "app_secret": self.app_secret},
            )
            
            if response.get("code") != 0:
                raise FeishuAuthError(f"Failed to get token: {response.get('msg')}")
            
            self._tenant_access_token = response.get("tenant_access_token")
            # Token typically expires in 2 hours, refresh 5 min before
            self._token_expires_at = now.replace(
                second=now.second + int(response.get("expire", 7200)) - self.token_refresh_buffer
            )
            
            return self._tenant_access_token
            
        except Exception as e:
            raise FeishuAuthError(f"Feishu authentication failed: {e}")
    
    async def create_record(self, record: TaskRecord, dry_run: bool = False) -> TaskRecord:
        """
        Create a new task record in Feishu bitable.
        
        Args:
            record: TaskRecord to create
            dry_run: If True, don't actually create
            
        Returns:
            Created TaskRecord with ID
        """
        if dry_run:
            logger.info(f"[DRY RUN] Would create record: {record.task_id}")
            return record
        
        try:
            await self._get_tenant_access_token()
            client = self._get_client()
            
            # Convert record to bitable fields
            fields = {
                "task_id": record.task_id,
                "raw_message": record.raw_message,
                "summary": record.summary,
                "tech_stack": ",".join(record.tech_stack) if record.tech_stack else "",
                "core_features": ",".join(record.core_features) if record.core_features else "",
                "status": record.status.value,
                "created_at": str(int(record.created_at.timestamp())),
            }
            
            request = CreateAppTableRecordRequest.builder()\
                .table_id(self.table_id)\
                .fields(fields)\
                .build()
            
            response = await asyncio.to_thread(
                client.bitable.v1.app_table_record.create,
                request
            )
            
            if response.code != 0:
                raise FeishuAPIError(f"Failed to create record: {response.msg}")
            
            logger.info(f"Created Feishu record: {record.task_id}")
            return record
            
        except Exception as e:
            logger.error(f"Failed to create Feishu record: {e}")
            raise
    
    async def get_record(self, record_id: str) -> TaskRecord:
        """
        Get a task record by ID.
        
        Args:
            record_id: Record ID
            
        Returns:
            TaskRecord
        """
        try:
            await self._get_tenant_access_token()
            client = self._get_client()
            
            request = GetAppTableRecordRequest.builder()\
                .table_id(self.table_id)\
                .record_id(record_id)\
                .build()
            
            response = await asyncio.to_thread(
                client.bitable.v1.app_table_record.get,
                request
            )
            
            if response.code != 0:
                raise FeishuRecordNotFoundError(f"Record not found: {record_id}")
            
            data = response.data.record.fields
            return TaskRecord(
                task_id=data.get("task_id", ""),
                raw_message=data.get("raw_message", ""),
                summary=data.get("summary", ""),
                tech_stack=data.get("tech_stack", "").split(",") if data.get("tech_stack") else [],
                status=TaskStatus(data.get("status", "pending")),
            )
            
        except FeishuRecordNotFoundError:
            raise
        except Exception as e:
            raise FeishuAPIError(f"Failed to get record: {e}")
    
    async def update_record(self, record: TaskRecord) -> TaskRecord:
        """
        Update an existing task record.
        
        Args:
            record: TaskRecord with updated values
            
        Returns:
            Updated TaskRecord
        """
        try:
            await self._get_tenant_access_token()
            client = self._get_client()
            
            fields = {
                "summary": record.summary,
                "tech_stack": ",".join(record.tech_stack) if record.tech_stack else "",
                "core_features": ",".join(record.core_features) if record.core_features else "",
                "status": record.status.value,
                "updated_at": str(int(datetime.now().timestamp())),
            }
            
            if record.code_repo_url:
                fields["code_repo_url"] = record.code_repo_url
            if record.executor_result:
                fields["executor_result"] = record.executor_result
            if record.error_message:
                fields["error_message"] = record.error_message
            
            request = UpdateAppTableRecordRequest.builder()\
                .table_id(self.table_id)\
                .record_id(record.task_id)\
                .fields(fields)\
                .build()
            
            response = await asyncio.to_thread(
                client.bitable.v1.app_table_record.update,
                request
            )
            
            if response.code != 0:
                raise FeishuAPIError(f"Failed to update record: {response.msg}")
            
            record.updated_at = datetime.now()
            logger.info(f"Updated Feishu record: {record.task_id}")
            return record
            
        except Exception as e:
            raise FeishuAPIError(f"Failed to update record: {e}")
    
    async def update_status(self, task_id: str, status: TaskStatus) -> TaskRecord:
        """
        Update task status.
        
        Args:
            task_id: Task ID
            status: New status
            
        Returns:
            Updated TaskRecord
        """
        try:
            record = await self.get_record(task_id)
            record.status = status
            record.updated_at = datetime.now()
            
            if status == TaskStatus.CONFIRMED:
                record.confirmed_at = datetime.now()
            elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                record.completed_at = datetime.now()
            
            return await self.update_record(record)
            
        except Exception as e:
            raise FeishuAPIError(f"Failed to update status: {e}")
