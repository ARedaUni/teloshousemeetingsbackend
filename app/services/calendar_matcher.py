from app.services.google_services import GoogleServiceManager
from app.core.config import get_settings
from datetime import datetime, timedelta
import pytz
from typing import List, Dict, Any, Optional
import numpy as np
import requests
from loguru import logger

settings = get_settings()

class CalendarMatcher:
    def __init__(self, google_service: GoogleServiceManager):
        self.google_service = google_service

    async def fetch_calendar_events(self, time_window_days: int = 365) -> List[Dict[str, Any]]:
        """Fetch calendar events within the specified time window."""
        now = datetime.utcnow().replace(tzinfo=pytz.UTC)
        start_range = (now - timedelta(days=time_window_days)).isoformat()
        end_range = (now + timedelta(days=time_window_days)).isoformat()

        try:
            events_result = self.google_service.calendar_service.events().list(
                calendarId='primary',  # Use primary calendar
                timeMin=start_range,
                timeMax=end_range,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            return events_result.get('items', [])
        except Exception as e:
            logger.error(f"Error fetching calendar events: {e}")
            return []

    async def match_transcript_to_event(
        self, 
        transcript: str, 
        recorded_date: datetime,
        events: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Match transcript to the most relevant calendar event."""
        if not transcript or not events:
            return None

        # First filter events by time proximity
        time_filtered_events = self._filter_events_by_time(events, recorded_date)
        if not time_filtered_events:
            return None

        # Get embeddings for transcript
        transcript_embedding = await self._get_embedding(transcript)
        if not transcript_embedding:
            return None

        best_match = None
        best_score = 0.0

        for event in time_filtered_events:
            event_text = f"{event.get('summary', '')} {event.get('description', '')}"
            event_embedding = await self._get_embedding(event_text)
            
            if not event_embedding:
                continue

            similarity = self._calculate_similarity(transcript_embedding, event_embedding)
            if similarity > best_score and similarity >= settings.MIN_SIMILARITY_THRESHOLD:
                best_score = similarity
                best_match = event

        return best_match

    def _filter_events_by_time(
        self, 
        events: List[Dict[str, Any]], 
        target_time: datetime
    ) -> List[Dict[str, Any]]:
        """Filter events by time proximity to the recording."""
        filtered_events = []
        
        for event in events:
            start_str = event['start'].get('dateTime', event['start'].get('date'))
            if 'T' in start_str:
                event_time = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
            else:
                event_time = datetime.fromisoformat(start_str)
                event_time = event_time.replace(tzinfo=pytz.UTC)

            time_diff = abs((event_time - target_time).total_seconds())
            if time_diff <= settings.TIME_WINDOW_DAYS * 24 * 3600:
                event['_time_diff'] = time_diff
                filtered_events.append(event)

        return sorted(filtered_events, key=lambda x: x['_time_diff'])

    async def _get_embedding(self, text: str) -> Optional[List[float]]:
        """Get text embedding using Jina AI API."""
        if not text.strip():
            return None

        try:
            response = requests.post(
                settings.JINA_EMBEDDING_URL,
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {settings.JINA_AUTH_TOKEN}',
                },
                json={
                    'model': settings.JINA_MODEL_NAME,
                    'input': [text],
                }
            )
            response.raise_for_status()
            result = response.json()
            return result.get('data', [{}])[0].get('embedding')
        except Exception as e:
            logger.error(f"Error getting embedding: {e}")
            return None

    def _calculate_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate similarity between two vectors."""
        try:
            vec1 = np.array(vec1, dtype=np.float64)
            vec2 = np.array(vec2, dtype=np.float64)
            
            # Cosine similarity
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            if norm1 == 0 or norm2 == 0:
                return 0.0
            cos_sim = np.dot(vec1, vec2) / (norm1 * norm2)
            
            return float((cos_sim + 1) / 2)  # Normalize to [0,1]
        except Exception as e:
            logger.error(f"Error calculating similarity: {e}")
            return 0.0