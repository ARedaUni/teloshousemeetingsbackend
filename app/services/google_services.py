from google.oauth2 import credentials
from google.oauth2.credentials import Credentials
from google.cloud import speech, storage
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from typing import Optional, List, Dict, Any
from loguru import logger
from app.core.config import get_settings
import json

settings = get_settings()

class GoogleServiceManager:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self._drive_service = None
        self._calendar_service = None
        self._speech_client = None
        self._storage_client = None

    def _get_credentials(self) -> Credentials:
        """Create credentials from access token."""
        return Credentials(
            token=self.access_token,
            scopes=[
                'https://www.googleapis.com/auth/drive.file',
                'https://www.googleapis.com/auth/calendar.readonly',
                'https://www.googleapis.com/auth/cloud-platform'
            ]
        )

    @property
    def drive_service(self):
        if not self._drive_service:
            self._drive_service = build('drive', 'v3', credentials=self._get_credentials())
        return self._drive_service

    @property
    def calendar_service(self):
        if not self._calendar_service:
            self._calendar_service = build('calendar', 'v3', credentials=self._get_credentials())
        return self._calendar_service

    @property
    def speech_client(self):
        if not self._speech_client:
            self._speech_client = speech.SpeechClient(credentials=self._get_credentials())
        return self._speech_client

    @property
    def storage_client(self):
        if not self._storage_client:
            self._storage_client = storage.Client(credentials=self._get_credentials())
        return self._storage_client

    async def validate_folder_access(self, folder_id: str) -> bool:
        """Validate that we have access to the specified folder."""
        try:
            self.drive_service.files().get(fileId=folder_id).execute()
            return True
        except Exception as e:
            logger.error(f"Error validating folder access: {e}")
            return False

    async def list_audio_files(self, folder_id: str) -> List[Dict[str, Any]]:
        """List audio files in the specified folder."""
        try:
            results = self.drive_service.files().list(
                q=f"'{folder_id}' in parents and trashed=false and mimeType contains 'audio/'",
                fields="files(id, name, createdTime, modifiedTime, mimeType)"
            ).execute()
            return results.get('files', [])
        except Exception as e:
            logger.error(f"Error listing audio files: {e}")
            raise