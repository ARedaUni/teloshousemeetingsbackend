from app.services.google_services import GoogleServiceManager
from app.core.config import get_settings
from loguru import logger
from google.cloud import speech
import asyncio
import os
import io
import tempfile
from typing import Optional, Callable
import ffmpeg

settings = get_settings()

class AudioProcessor:
    def __init__(
        self, 
        google_service: GoogleServiceManager,
        status_callback: Callable[[str, Optional[dict]], None]
    ):
        self.google_service = google_service
        self.status_callback = status_callback
        self.temp_dir = tempfile.mkdtemp()

    async def process_file(self, file_id: str, file_name: str) -> Optional[str]:
        """Process a single audio file."""
        local_path = os.path.join(self.temp_dir, file_name)
        wav_path = f"{local_path}.wav"

        try:
            await self.status_callback(f"Downloading {file_name}...")
            await self._download_file(file_id, local_path)

            await self.status_callback(f"Converting {file_name} to WAV format...")
            await self._convert_to_wav(local_path, wav_path)

            await self.status_callback(f"Transcribing {file_name}...")
            transcript = await self._transcribe_audio(wav_path)

            return transcript

        except Exception as e:
            logger.error(f"Error processing file {file_name}: {e}")
            await self.status_callback(f"Error processing {file_name}: {str(e)}")
            return None

        finally:
            # Cleanup temporary files
            for path in [local_path, wav_path]:
                if os.path.exists(path):
                    os.remove(path)

    async def _download_file(self, file_id: str, local_path: str):
        """Download file from Google Drive."""
        request = self.google_service.drive_service.files().get_media(fileId=file_id)
        with open(local_path, 'wb') as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()

    async def _convert_to_wav(self, input_path: str, output_path: str):
        """Convert audio file to WAV format."""
        try:
            stream = ffmpeg.input(input_path)
            stream = ffmpeg.output(
                stream,
                output_path,
                acodec='pcm_s16le',
                ac=1,
                ar=48000,
                audio_bitrate='192k',
                loglevel='warning'
            )
            await asyncio.to_thread(ffmpeg.run, stream, capture_stdout=True, capture_stderr=True)
        except Exception as e:
            logger.error(f"FFmpeg conversion error: {e}")
            raise

    async def _transcribe_audio(self, audio_path: str) -> str:
        """Transcribe audio file using Google Speech-to-Text."""
        # Upload to GCS temporarily
        bucket = self.google_service.storage_client.bucket(settings.BUCKET_NAME)
        blob_name = f"temp_audio_{os.path.basename(audio_path)}"
        blob = bucket.blob(blob_name)

        try:
            # Upload file
            await asyncio.to_thread(blob.upload_from_filename, audio_path)
            gcs_uri = f"gs://{settings.BUCKET_NAME}/{blob_name}"

            # Configure speech recognition
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=48000,
                language_code="en-US",
                enable_automatic_punctuation=True,
                model='video',
                use_enhanced=True,
                diarization_config=speech.SpeakerDiarizationConfig(
                    enable_speaker_diarization=True,
                    min_speaker_count=1,
                    max_speaker_count=10,
                )
            )

            audio = speech.RecognitionAudio(uri=gcs_uri)
            operation = await asyncio.to_thread(
                self.google_service.speech_client.long_running_recognize,
                config=config,
                audio=audio
            )

            await self.status_callback("Transcription in progress...")
            result = await asyncio.to_thread(operation.result)

            transcript_parts = []
            current_speaker = None

            for result in result.results:
                for alternative in result.alternatives:
                    transcript_parts.append(alternative.transcript)

            return " ".join(transcript_parts)

        finally:
            # Cleanup GCS file
            await asyncio.to_thread(blob.delete)