from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends
from app.models.schemas import ProcessingRequest, ProcessingStatus
from app.services.google_services import GoogleServiceManager
from app.services.audio_processor import AudioProcessor
from app.services.calendar_matcher import CalendarMatcher
from app.services.summary_generator import SummaryGenerator
from app.api.websocket import manager
from app.core.config import get_settings
from typing import Dict, Any
import asyncio
import uuid
from loguru import logger

router = APIRouter()
settings = get_settings()

async def process_audio_files(
    client_id: str,
    google_service: GoogleServiceManager,
    request: ProcessingRequest
):
    """Process audio files with real-time status updates."""
    try:
        # Initialize services
        async def status_callback(message: str, data: Dict[str, Any] = None):
            await manager.send_status(client_id, message, data)

        audio_processor = AudioProcessor(google_service, status_callback)
        calendar_matcher = CalendarMatcher(google_service)
        summary_generator = SummaryGenerator(google_service)

        # Validate folder access
        await status_callback("Validating folder access...")
        for folder_id in [request.audio_folder_id, request.summary_folder_id]:
            if not await google_service.validate_folder_access(folder_id):
                raise Exception(f"Cannot access folder: {folder_id}")

        # Fetch audio files
        await status_callback("Fetching audio files...")
        files = await google_service.list_audio_files(request.audio_folder_id)
        if not files:
            await status_callback("No audio files found in the specified folder.")
            return

        # Fetch calendar events once
        await status_callback("Fetching calendar events...")
        calendar_events = await calendar_matcher.fetch_calendar_events()

        # Process each file
        for file in files:
            file_id = file['id']
            file_name = file['name']

            try:
                # Check for existing summary
                if await google_service.check_summary_exists(
                    request.summary_folder_id, 
                    file_id
                ):
                    await status_callback(
                        f"Skipping {file_name} - summary already exists"
                    )
                    continue

                # Process audio file
                transcript = await audio_processor.process_file(file_id, file_name)
                if not transcript:
                    continue

                # Match with calendar event
                await status_callback(f"Matching {file_name} with calendar events...")
                calendar_context = None
                if calendar_events:
                    recorded_date = file.get('createdTime')
                    if recorded_date:
                        calendar_context = await calendar_matcher.match_transcript_to_event(
                            transcript,
                            recorded_date,
                            calendar_events
                        )

                # Generate summary
                await status_callback(f"Generating summary for {file_name}...")
                summary = await summary_generator.generate_summary(
                    transcript,
                    calendar_context
                )

                if summary:
                    # Upload summary
                    await status_callback(f"Uploading summary for {file_name}...")
                    success = await google_service.upload_summary(
                        request.summary_folder_id,
                        summary,
                        file_name,
                        file_id
                    )
                    if success:
                        await status_callback(
                            f"Successfully processed {file_name}",
                            {"file_id": file_id}
                        )
                    else:
                        await status_callback(
                            f"Failed to upload summary for {file_name}"
                        )

            except Exception as e:
                logger.error(f"Error processing {file_name}: {e}")
                await status_callback(f"Error processing {file_name}: {str(e)}")
                continue

        await status_callback("Processing completed")

    except Exception as e:
        logger.error(f"Processing error: {e}")
        await manager.send_error(client_id, str(e))
    finally:
        manager.disconnect(client_id)

@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_json()
            if data["type"] == "start_processing":
                request = ProcessingRequest(**data["data"])
                google_service = GoogleServiceManager(request.access_token)
                
                # Create and register the processing task
                task = asyncio.create_task(
                    process_audio_files(client_id, google_service, request)
                )
                manager.register_task(client_id, task)
                
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await manager.send_error(client_id, str(e))
        manager.disconnect(client_id)