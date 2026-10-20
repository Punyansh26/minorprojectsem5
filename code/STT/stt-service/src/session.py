
"""
One SttSession = one caller's live audio stream.

State machine:

    SILENCE
        ↓ VAD detects speech
    SPEAKING
        ↓ periodic partial transcription
    PARTIAL
        ↓ VAD detects enough silence
    FINAL
        ↓
    SILENCE

All ASR calls are blocking (CPU/GPU bound), so they are executed in a
shared ThreadPoolExecutor. This prevents ASR inference from directly
blocking the asyncio event loop.
"""

from __future__ import annotations

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from enum import Enum, auto

import numpy as np

from src.asr import get_engine, logprob_to_confidence
from src.config import settings
from src.prefix_commit import PrefixCommitter
from src.schemas import STTEvent, EventType
from src.turn_detector import get_turn_detector, should_finalize as eou_should_finalize
from src.vad import SpeechDetector


# ---------------------------------------------------------------------------
# Shared ASR executor
# ---------------------------------------------------------------------------
# One executor is shared by all sessions so the number of simultaneous
# CPU-heavy ASR operations is bounded.

_EXECUTOR = ThreadPoolExecutor(
    max_workers=settings.ASR_WORKER_THREADS
)

BYTES_PER_SAMPLE = 2  # 16-bit PCM


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

class _State(Enum):
    SILENCE = auto()
    SPEAKING = auto()


class SttSession:
    """
    Represents one live caller's STT session.
    """

    def __init__(self, session_id: str):
        self.session_id = session_id

        self._vad = SpeechDetector()
        self._state = _State.SILENCE

        # Streaming prefix commit (LocalAgreement-N). One committer per utterance.
        self._committer = PrefixCommitter(n=settings.PREFIX_COMMIT_N)

        # Semantic EOU: last probed completion probability for the current
        # utterance (None until first probe / when the model is unavailable).
        self._last_eou_prob: float | None = None

        # Raw PCM16 bytes for the current utterance.
        self._buffer = bytearray()

        # Timing.
        self._utterance_start_ms: float = 0.0
        self._last_partial_emit_ts: float = 0.0
        self._silence_started_ts: float | None = None

        # Statistics.
        self._utterance_counter = 0
        self._total_bytes_received = 0

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    async def start(self) -> STTEvent:
        """Return a session-started event."""
        return STTEvent(
            type=EventType.SESSION_STARTED,
            session_id=self.session_id,
        )

    async def process_chunk(
        self,
        pcm16_bytes: bytes,
    ) -> list[STTEvent]:
        """
        Feed one chunk of raw PCM16 audio.

        Returns zero or more STT events:
            SPEECH_STARTED
            PARTIAL
            FINAL
        """

        if not pcm16_bytes:
            return []

        self._total_bytes_received += len(pcm16_bytes)

        events: list[STTEvent] = []

        # ---------------------------------------------------------------
        # Run VAD
        # ---------------------------------------------------------------

        vad_events = self._vad.process(pcm16_bytes)
        now = time.monotonic()

        speech_detected_this_chunk = any(
            "start" in event for event in vad_events
        )

        silence_detected_this_chunk = any(
            "end" in event for event in vad_events
        )

        # ---------------------------------------------------------------
        # SILENCE -> SPEAKING
        # ---------------------------------------------------------------

        if (
            speech_detected_this_chunk
            and self._state == _State.SILENCE
        ):
            self._state = _State.SPEAKING

            self._utterance_start_ms = self._elapsed_audio_ms()

            self._buffer.clear()

            self._silence_started_ts = None

            # Fresh prefix-commit + EOU state for the new utterance.
            self._committer.reset()
            self._last_eou_prob = None

            # Reset partial timer for the new utterance.
            self._last_partial_emit_ts = now

            events.append(
                STTEvent(
                    type=EventType.SPEECH_STARTED,
                    session_id=self.session_id,
                    interrupt_previous_response=True,
                )
            )

        # ---------------------------------------------------------------
        # SPEAKING
        # ---------------------------------------------------------------

        if self._state == _State.SPEAKING:

            # Add current audio to utterance buffer.
            self._buffer.extend(pcm16_bytes)

            # -----------------------------------------------------------
            # Track silence
            # -----------------------------------------------------------

            if silence_detected_this_chunk:
                if self._silence_started_ts is None:
                    self._silence_started_ts = now

            elif speech_detected_this_chunk:
                # Speech resumed.
                self._silence_started_ts = None

            # -----------------------------------------------------------
            # Calculate timing
            # -----------------------------------------------------------

            utterance_ms = self._buffer_ms()

            silence_ms = (
                (now - self._silence_started_ts) * 1000
                if self._silence_started_ts is not None
                else 0
            )

            # -----------------------------------------------------------
            # Decide whether utterance is finished
            # -----------------------------------------------------------
            #
            # Chapter 03 §3.2: gate finalisation on a semantic EOU classifier
            # when one is available, with a silence safety cap so an absent or
            # low-confidence model can never hang the turn. With EOU disabled or
            # unavailable this reduces exactly to the legacy silence endpoint
            # (EOU_MAX_SILENCE_MS defaults to the old END_OF_SPEECH_SILENCE_MS).

            if settings.EOU_ENABLED and silence_ms >= settings.EOU_MIN_SILENCE_MS:
                # Only probe the (blocking) model once we are in the silence
                # window and have not yet got a confident completion.
                if self._last_eou_prob is None or self._last_eou_prob < settings.EOU_THRESHOLD:
                    self._last_eou_prob = await self._probe_eou()

            should_finalize = eou_should_finalize(
                silence_ms=silence_ms,
                utterance_ms=utterance_ms,
                eou_p=self._last_eou_prob if settings.EOU_ENABLED else None,
                min_silence_ms=settings.EOU_MIN_SILENCE_MS,
                max_silence_ms=settings.EOU_MAX_SILENCE_MS,
                eou_tau=settings.EOU_THRESHOLD,
                max_utterance_ms=settings.MAX_UTTERANCE_MS,
            )

            # -----------------------------------------------------------
            # FINAL
            # -----------------------------------------------------------

            if should_finalize:

                final_event = await self._finalize()

                if final_event is not None:
                    events.append(final_event)

            # -----------------------------------------------------------
            # PARTIAL
            # -----------------------------------------------------------

            elif (
                (now - self._last_partial_emit_ts) * 1000
                >= settings.PARTIAL_INTERVAL_MS
            ):

                if utterance_ms >= settings.MIN_SPEECH_MS_FOR_PARTIAL:

                    partial_event = await self._emit_partial()

                    if partial_event is not None:
                        events.append(partial_event)

                self._last_partial_emit_ts = now

        return events

    async def flush(self) -> STTEvent | None:
        """
        Force-finalize the current utterance.

        Called when the client explicitly stops or disconnects.
        """

        if (
            self._state == _State.SPEAKING
            and len(self._buffer) > 0
        ):
            return await self._finalize()

        return None

    # -----------------------------------------------------------------------
    # Audio helpers
    # -----------------------------------------------------------------------

    def _buffer_ms(self) -> float:
        """Return current utterance duration in milliseconds."""

        n_samples = len(self._buffer) / BYTES_PER_SAMPLE

        return (
            n_samples / settings.SAMPLE_RATE
        ) * 1000

    def _elapsed_audio_ms(self) -> float:
        """Return total received audio duration in milliseconds."""

        n_samples = (
            self._total_bytes_received
            / BYTES_PER_SAMPLE
        )

        return (
            n_samples / settings.SAMPLE_RATE
        ) * 1000

    def _bytes_to_float32(
        self,
        raw: bytes,
    ) -> np.ndarray:
        """Convert PCM16 bytes to float32 [-1, 1]."""

        return (
            np.frombuffer(
                raw,
                dtype=np.int16,
            )
            .astype(np.float32)
            / 32768.0
        )

    # -----------------------------------------------------------------------
    # Semantic end-of-turn probe
    # -----------------------------------------------------------------------

    async def _probe_eou(self) -> float | None:
        """Run the EOU classifier on the current buffer, off the event loop.

        Returns ``p_complete`` in [0, 1], or ``None`` when no model is available
        (disabled / weights absent / error) so the caller falls back to silence.
        The model reads the last 8 s internally, but a short buffer carries no
        completion signal, so we skip the probe below MIN_FINAL_AUDIO_MS.
        """
        if self._buffer_ms() < settings.MIN_FINAL_AUDIO_MS:
            return None

        audio = self._bytes_to_float32(bytes(self._buffer))

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            _EXECUTOR,
            lambda: get_turn_detector().predict(audio),
        )
        return result.p_complete

    # -----------------------------------------------------------------------
    # Partial transcription
    # -----------------------------------------------------------------------

    async def _emit_partial(
        self,
    ) -> STTEvent | None:
        """
        Generate a partial transcript.

        Only the most recent PARTIAL_WINDOW_MS of audio is transcribed.
        This prevents partial inference from becoming progressively slower
        as the utterance grows.
        """

        window_bytes = (
            int(
                settings.PARTIAL_WINDOW_MS
                / 1000
                * settings.SAMPLE_RATE
            )
            * BYTES_PER_SAMPLE
        )

        if len(self._buffer) > window_bytes:
            windowed = bytes(
                self._buffer[-window_bytes:]
            )
        else:
            windowed = bytes(self._buffer)

        audio = self._bytes_to_float32(windowed)

        # Run blocking ASR outside the asyncio event loop.
        loop = asyncio.get_running_loop()

        transcript = await loop.run_in_executor(
            _EXECUTOR,
            lambda: get_engine().transcribe(
                audio,
                fast=True,
            ),
        )

        if not transcript.text:
            return None

        # LocalAgreement-N: freeze the stable prefix, expose the revisable tail.
        # When disabled, committed/pending stay empty and `text` is unchanged, so
        # existing clients see exactly the old windowed partial behaviour.
        committed_text = ""
        pending_text = ""
        if settings.PREFIX_COMMIT_ENABLED:
            result = self._committer.update(transcript.text)
            committed_text = result.committed_text
            pending_text = result.pending_text

        return STTEvent(
            type=EventType.PARTIAL,
            session_id=self.session_id,
            text=transcript.text,
            committed_text=committed_text,
            pending_text=pending_text,
            start_ms=int(self._utterance_start_ms),
            end_ms=int(self._elapsed_audio_ms()),
            confidence=logprob_to_confidence(
                transcript.avg_logprob
            ),
        )

    # -----------------------------------------------------------------------
    # Final transcription
    # -----------------------------------------------------------------------

    async def _finalize(
        self,
    ) -> STTEvent | None:
        """
        Finalize the current utterance.

        IMPORTANT:
        This method is intentionally inside SttSession.
        """

        # Copy the current audio before resetting the session.
        audio = self._bytes_to_float32(
            bytes(self._buffer)
        )

        end_ms = self._elapsed_audio_ms()

        # The EOU probability that triggered this finalisation (None on the pure
        # silence-timer path), captured before per-utterance state is cleared.
        eou_prob = self._last_eou_prob if settings.EOU_ENABLED else None

        # ---------------------------------------------------------------
        # Reset session state immediately.
        # ---------------------------------------------------------------

        self._buffer.clear()

        self._state = _State.SILENCE

        self._silence_started_ts = None

        self._last_partial_emit_ts = 0.0

        self._committer.reset()
        self._last_eou_prob = None

        self._vad.reset()

        # ---------------------------------------------------------------
        # Ignore extremely short audio.
        # ---------------------------------------------------------------

        minimum_samples = (
            settings.SAMPLE_RATE
            * (settings.MIN_FINAL_AUDIO_MS / 1000)
        )

        if len(audio) < minimum_samples:
            return None

        # ---------------------------------------------------------------
        # Final ASR
        # ---------------------------------------------------------------

        loop = asyncio.get_running_loop()

        transcript = await loop.run_in_executor(
            _EXECUTOR,
            lambda: get_engine().transcribe(
                audio,
                fast=False,
            ),
        )

        # ---------------------------------------------------------------
        # Validate transcript
        # ---------------------------------------------------------------

        if not transcript.text:
            return None

        # Prevent Whisper hallucinations on silence/noise.
        if (
            transcript.no_speech_prob
            >= settings.NO_SPEECH_PROB_THRESHOLD
        ):
            return None

        # ---------------------------------------------------------------
        # Create FINAL event
        # ---------------------------------------------------------------

        self._utterance_counter += 1

        return STTEvent(
            type=EventType.FINAL,
            session_id=self.session_id,
            text=transcript.text,
            start_ms=int(self._utterance_start_ms),
            end_ms=int(end_ms),
            confidence=logprob_to_confidence(
                transcript.avg_logprob
            ),
            utterance_id=self._utterance_counter,
            eou_prob=eou_prob,
        )

