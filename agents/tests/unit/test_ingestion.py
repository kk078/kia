"""Tests for multi-modal ingestion components."""

import pytest

from brain_knowledge.ingestion.audio import AudioTranscriber
from brain_knowledge.ingestion.ocr import OCRProcessor
from brain_knowledge.ingestion.vision import VisionProcessor


class TestOCRProcessor:
    """Test OCR processor functionality."""

    @pytest.fixture
    def ocr(self) -> OCRProcessor:
        """Create OCR processor instance."""
        return OCRProcessor()

    @pytest.mark.asyncio
    async def test_process_nonexistent_image(self, ocr: OCRProcessor) -> None:
        """Test processing non-existent image."""
        with pytest.raises(FileNotFoundError):
            await ocr.process_image("/nonexistent/image.png")

    @pytest.mark.asyncio
    async def test_process_batch_empty(self, ocr: OCRProcessor) -> None:
        """Test processing empty batch."""
        results = await ocr.process_batch([])
        assert results == []


class TestAudioTranscriber:
    """Test audio transcriber functionality."""

    @pytest.fixture
    def transcriber(self) -> AudioTranscriber:
        """Create transcriber instance."""
        return AudioTranscriber()

    @pytest.mark.asyncio
    async def test_transcribe_nonexistent_file(self, transcriber: AudioTranscriber) -> None:
        """Test transcribing non-existent file."""
        with pytest.raises(FileNotFoundError):
            await transcriber.transcribe("/nonexistent/audio.mp3")

    @pytest.mark.asyncio
    async def test_transcribe_with_timestamps_nonexistent(
        self, transcriber: AudioTranscriber
    ) -> None:
        """Test transcribing with timestamps for non-existent file."""
        with pytest.raises(FileNotFoundError):
            await transcriber.transcribe_with_timestamps("/nonexistent/audio.mp3")


class TestVisionProcessor:
    """Test vision processor functionality."""

    @pytest.fixture
    def vision(self) -> VisionProcessor:
        """Create vision processor instance."""
        return VisionProcessor()

    @pytest.mark.asyncio
    async def test_describe_nonexistent_image(self, vision: VisionProcessor) -> None:
        """Test describing non-existent image."""
        with pytest.raises(FileNotFoundError):
            await vision.describe_image("/nonexistent/image.png")

    @pytest.mark.asyncio
    async def test_extract_text_nonexistent(self, vision: VisionProcessor) -> None:
        """Test extracting text from non-existent image."""
        with pytest.raises(FileNotFoundError):
            await vision.extract_text_from_image("/nonexistent/image.png")

    @pytest.mark.asyncio
    async def test_analyze_nonexistent(self, vision: VisionProcessor) -> None:
        """Test analyzing non-existent image."""
        with pytest.raises(FileNotFoundError):
            await vision.analyze_image("/nonexistent/image.png", "What is this?")
