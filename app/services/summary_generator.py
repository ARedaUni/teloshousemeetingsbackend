from app.services.google_services import GoogleServiceManager
from app.core.config import get_settings
from typing import Dict, Optional
from loguru import logger
import vertexai
from vertexai.generative_models import GenerativeModel

settings = get_settings()

class SummaryGenerator:
    def __init__(self, google_service: GoogleServiceManager):
        self.google_service = google_service
        self._model = None

    @property
    def model(self):
        if self._model is None:
            vertexai.init(
                project=settings.PROJECT_ID,
                location=settings.LOCATION
            )
            self._model = GenerativeModel("gemini-1.5-flash-002")
        return self._model

    async def generate_summary(
        self, 
        transcript: str, 
        calendar_context: Optional[Dict] = None
    ) -> Optional[str]:
        """Generate a meeting summary using Gemini."""
        try:
            calendar_info = self._format_calendar_context(calendar_context) if calendar_context else ""
            
            prompt = self._create_summary_prompt(transcript, calendar_info)
            response = await self._generate_with_retry(prompt)
            
            return response.text if response and response.text else None

        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return None

    def _format_calendar_context(self, context: Dict) -> str:
        """Format calendar context for the prompt."""
        return f"""
        Meeting Context:
        - Event: {context.get('summary', 'N/A')}
        - Date: {context.get('start', 'N/A')}
        - Location: {context.get('location', 'N/A')}
        - Organizer: {context.get('organizer', {}).get('email', 'N/A')}
        - Attendees: {', '.join(context.get('attendees', []))}
        - Description: {context.get('description', 'N/A')}
        """

    def _create_summary_prompt(self, transcript: str, calendar_info: str = "") -> str:
        """Create the prompt for summary generation."""
        return f"""
        Create a visually appealing and well-structured business meeting summary using the following format:

        ⭐️ EXECUTIVE SUMMARY
        ══════════════════
        Brief 2-3 line overview of the meeting's key achievement or main purpose.

        📅 MEETING DETAILS
        ════════════════
        • Date & Time: [Format: Day, Date at Time]
        • Duration: [X hours/minutes]
        • Location: [Physical/Virtual location]
        • Meeting Type: [Format/Purpose]

        👥 KEY PARTICIPANTS
        ════════════════
        • Chair: [Meeting leader name/role]
        • Core Attendees: [Key people]
        • Teams Represented: [Departments/Groups]

        🎯 MAIN OBJECTIVES
        ════════════════
        1. [Primary goal]
        2. [Secondary goal]
        3. [Additional goals if any]

        💫 KEY DISCUSSION POINTS
        ═══════════════════
        1. [Topic 1]
           • Detailed point
           • Key insights
           • Concerns raised

        2. [Topic 2]
           • Detailed point
           • Key insights
           • Concerns raised

        📊 DECISIONS & OUTCOMES
        ══════════════════
        ✓ [Major decision 1]
        ✓ [Major decision 2]
        ✓ [Major decision 3]

        ⚡️ ACTION ITEMS
        ═════════════
        1. [Action Item]
           • Owner: [Name]
           • Deadline: [Date]
           • Dependencies: [If any]

        🔄 NEXT STEPS
        ════════════
        • [Immediate next step]
        • [Follow-up action]
        • [Future consideration]

        {calendar_info}

        Content to analyze:
        {transcript}
        """

    async def _generate_with_retry(self, prompt: str, max_retries: int = 3) -> Optional[Any]:
        """Generate summary with retry logic."""
        for attempt in range(max_retries):
            try:
                return self.model.generate_content(prompt)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"Retry {attempt + 1}/{max_retries} failed: {e}")
                await asyncio.sleep(1 * (attempt + 1))  # Exponential backoff