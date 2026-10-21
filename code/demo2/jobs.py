"""Bound shared model work while Streamlit independently renders reviewed results."""
from collections import Counter, deque
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import dataclass, field
from functools import lru_cache
from hashlib import sha256
from threading import Condition, Event, Thread
from time import monotonic

import agent_bridge
import settings as cfg
import speech
from storage import Store

TERMINAL = {"complete", "failed", "cancelled"}

# FutureWork 10 §1.4 — cheap, local, admission-time predictor for short-turn priority and
# deadline-aware shedding. It must run *before* any STT/model work, so it cannot use the
# agent's real router (router_path is computed inside agent_bridge.ask, post-admission).
# It is a deliberately conservative TEXT heuristic: it only flags turns that are almost
# certainly trivial (greetings, thanks, yes/no, very short utterances with 0 expected LLM
# calls). Anything uncertain — and every voice recording, whose text is unknown until it is
# transcribed — is treated as a normal/heavy turn. Mis-classifying a heavy turn as short would
# let it jump the queue; erring toward "heavy" keeps that from happening. This reorders *when*
# turns run and sheds overload earlier; it never changes *what* a turn computes.
_SHORT_TURN_MARKERS = (
    "hi", "hii", "hey", "hello", "helo", "namaste", "namaskar", "yes", "yeah", "yep", "no",
    "nope", "ok", "okay", "thanks", "thank you", "thankyou", "thx", "ty", "bye", "goodbye",
    "good morning", "good evening", "good afternoon", "good night", "welcome",
    "नमस्ते", "नमस्कार", "धन्यवाद", "शुक्रिया", "हाँ", "हां", "नहीं", "ठीक", "अलविदा", "सुप्रभात",
)


def predict_short_turn(text, max_chars):
    """Return True only for turns almost certain to need 0 LLM calls. Conservative by design."""
    if not text:
        return False
    stripped = text.strip()
    if not stripped:
        return False
    # A trailing greeting/thanks is the overwhelmingly common trivial case.
    lowered = stripped.lower().rstrip(" .!?।,")
    if lowered in _SHORT_TURN_MARKERS:
        return True
    # Very short, question-mark-free utterances are treated as trivial smalltalk; anything with
    # a question mark or longer than the short-turn budget is left to the normal (heavy) path.
    if "?" in stripped or len(stripped) > max_chars:
        return False
    return any(lowered.startswith(marker) for marker in _SHORT_TURN_MARKERS)


def predicted_service_seconds(is_short):
    """Planning estimate S for deadline-aware shedding (FutureWork 10 §1.2). [Estimated]"""
    return cfg.PREDICTED_SHORT_TURN_SECONDS if is_short else cfg.PREDICTED_HEAVY_TURN_SECONDS


@dataclass
class Job:
    session_id: str
    turn_id: str
    question: str
    profile: dict
    provider: str
    voice: str
    speed: float
    spoken: bool
    online_speech: bool
    recording: bytes | None = None
    input_language: str = "Hindi"
    submitted: float = field(default_factory=monotonic)
    cancelled: Event = field(default_factory=Event)
    stage: str = "queued"
    result: dict = field(default_factory=dict)
    timings: dict = field(default_factory=dict)
    error_code: str | None = None
    speech_deadline: float = 0
    short_turn: bool = False


class JobManager:
    """One reasoning owner and one speech worker share models, never browser state."""

    def __init__(self, store=None, start=True):
        self.store = store or Store()
        self.runtime_lock = self.store.acquire_runtime()
        self.condition = Condition()
        self.queue, self.jobs = deque(), {}
        # FutureWork 10 §1.4: a second, higher-priority deque for predicted short turns. The
        # reasoning worker drains it before the normal queue so a 50 ms "thanks" never waits
        # behind a ~18 s knowledge turn. Both feed the SAME single worker, so this reorders
        # scheduling only — it does not add a parallel model slot (T0 keeps NUM_PARALLEL=1).
        self.priority = deque()
        self.counters = Counter()
        self.closed = False
        self.speech_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="demo-speech")
        self.worker = Thread(target=self._loop, name="demo-reasoning", daemon=True)
        self.maintenance = Thread(target=self._maintenance, name="demo-maintenance", daemon=True)
        if start:
            self.worker.start()
            self.maintenance.start()

    def submit(self, session_id, turn_id, question, profile, provider, voice, speed,
               spoken=True, online_speech=False, recording=None, input_language="Hindi"):
        """Admit once, before STT/model work; reject overload rather than queue indefinitely."""
        key = (session_id,turn_id)
        with self.condition:
            if key in self.jobs and self.jobs[key].stage not in {"failed", "cancelled"}:
                return turn_id
            if any(j.session_id == session_id and j.stage not in TERMINAL for j in self.jobs.values()):
                raise ValueError("conversation_busy")
            if sum(j.stage not in TERMINAL for j in self.jobs.values()) >= cfg.QUEUE_CAPACITY + 1:
                self.counters["overload"] += 1
                raise ValueError("busy")
            # FutureWork 10 §1.4 — classify this turn cheaply from its text (a voice recording's
            # text is unknown until transcription, so it is always treated as heavy).
            is_short = bool(cfg.SHORT_TURN_PRIORITY_ENABLED and recording is None
                            and predict_short_turn(question, cfg.SHORT_TURN_MAX_CHARS))
            # Deadline-aware shedding: a short turn always fits, so only heavy admissions are
            # checked. Predicted completion = (work already queued ahead) + (this turn's own
            # predicted service). If that exceeds the queue deadline, reject now with a fast
            # "busy" instead of admitting the turn only to fail queue_timeout/deadline later.
            if cfg.DEADLINE_SHEDDING_ENABLED and not is_short:
                ahead = sum(predicted_service_seconds(j.short_turn)
                            for j in self.jobs.values() if j.stage in {"queued", "reasoning", "transcribing"})
                predicted = ahead + predicted_service_seconds(False)
                if predicted > cfg.QUEUE_TIMEOUT_SECONDS:
                    self.counters["overload_predicted"] += 1
                    raise ValueError("busy")
            payload = {"question": question, "profile": profile, "provider": provider,
                       "recording_sha256": sha256(recording).hexdigest() if recording else None,
                       "input_language": input_language if recording else None}
            result = self.store.request(session_id,turn_id,payload)
            job = Job(session_id,turn_id,question,dict(profile),provider,voice,speed,spoken,
                      online_speech,recording,input_language)
            job.short_turn = is_short
            if result is not None:
                job.result, job.stage = result,"complete"
            elif is_short:
                self.priority.append(job)
                self.counters["admitted:short"] += 1
            else:
                self.queue.append(job)
                self.counters["admitted:normal"] += 1
            self.jobs[key] = job
            # Completed audio is transient and bounded globally; durable text remains in Store.
            finished = [k for k,j in self.jobs.items() if j.stage in TERMINAL]
            for old in finished[:-128]:
                del self.jobs[old]
            # notify_all: maintenance waits on this Condition too, and a single notify() can
            # wake it instead of the reasoning worker, stranding the turn until queue_timeout.
            self.condition.notify_all()
            return turn_id

    def snapshot(self, session_id, turn_id):
        """Return a copy for the UI; opaque session ownership is never a student reference."""
        with self.condition:
            job = self.jobs.get((session_id,turn_id))
            if job is None:
                return None
            if job.stage not in TERMINAL:
                limit = cfg.QUEUE_TIMEOUT_SECONDS if job.stage == "queued" else cfg.TURN_TIMEOUT_SECONDS
                if job.stage != "speech" and monotonic()-job.submitted > limit:
                    job.cancelled.set()
                    job.error_code = "queue_timeout" if job.stage == "queued" else "deadline_exceeded"
            return {"id": job.turn_id, "question": job.question, "stage": job.stage,
                    "error_code": job.error_code, "timings": dict(job.timings), **deepcopy(job.result)}

    def cancel(self, session_id, turn_id=None):
        """Suppress late results immediately; executing work still owns its resource slot."""
        with self.condition:
            for job in self.jobs.values():
                if job.session_id == session_id and (turn_id is None or job.turn_id == turn_id) and job.stage not in TERMINAL:
                    job.cancelled.set()
                    if job.stage == "queued":
                        job.stage = "cancelled"
                        job.recording = None
            self.condition.notify_all()

    def delete(self, session_id):
        """Wait for cancelled work to drain before erasing its saved state."""
        self.cancel(session_id)
        with self.condition:
            if any(j.session_id == session_id and j.stage not in TERMINAL for j in self.jobs.values()):
                return False
            self.store.delete(session_id)
            for key in [k for k in self.jobs if k[0] == session_id]:
                del self.jobs[key]
            return True

    def backup(self):
        """Take a consistent multi-database backup only while all jobs are idle."""
        with self.condition:
            if any(j.stage not in TERMINAL for j in self.jobs.values()):
                raise ValueError("busy")
            return self.store.backup()

    def _stage(self, job, stage):
        with self.condition:
            job.stage = stage

    def _loop(self):
        while True:
            with self.condition:
                self.condition.wait_for(lambda: self.priority or self.queue or self.closed)
                if self.closed:
                    return
                # Priority (predicted short) turns are drained before the normal queue.
                job = self.priority.popleft() if self.priority else self.queue.popleft()
            if job.cancelled.is_set():
                self._stage(job,"cancelled")
                continue
            if monotonic()-job.submitted >= cfg.QUEUE_TIMEOUT_SECONDS:
                job.error_code = "queue_timeout"
                self._stage(job,"failed")
                continue
            try:
                self._run(job)
            except BaseException:
                # A dead worker would strand every later turn in "queued" until queue_timeout.
                with self.condition:
                    job.error_code = job.error_code or "turn_failed"
                    job.recording = None
                    job.stage = "cancelled" if job.cancelled.is_set() else "failed"

    def _run(self, job):
        from assistant.operations import Operation, operation_context, check
        operation = Operation(job.session_id,job.turn_id,job.submitted+cfg.TURN_TIMEOUT_SECONDS,
                              cancelled=job.cancelled,progress=lambda s:self._stage(job,s))
        job.timings["queue_seconds"] = monotonic()-job.submitted
        try:
            with operation_context(operation):
                if job.recording is not None:
                    check("transcribing")
                    started = monotonic()
                    job.question = speech.transcribe(job.recording,job.input_language)
                    job.timings["stt_seconds"] = monotonic()-started
                    job.recording = None
                    if not job.question:
                        raise ValueError("no_speech")
                check("reasoning")
                started = monotonic()
                result = agent_bridge.ask(job.question,job.session_id,job.profile,
                                          provider=job.provider,turn_id=job.turn_id)
                check()
                result.update(id=job.turn_id,question=job.question,audio=None,audio_error=None,error=None,
                              llm_provider=job.provider,agent_seconds=monotonic()-started)
                self.store.complete(job.session_id,job.turn_id,result)
                self.store.compact(job.session_id)
                with self.condition:
                    job.timings["reviewed_text_seconds"] = monotonic()-job.submitted
                    job.result = result
                    job.result["provider_attempts"] = list(operation.attempts)
                    metrics = result.get("rag_metrics") or {}
                    self.counters["router:" + str(metrics.get("router_path","unknown"))] += 1
                    if metrics.get("router_fallback"):
                        self.counters["fallback:" + metrics["router_fallback"]] += 1
                if job.spoken and result.get("answer_text"):
                    job.speech_deadline = monotonic()+cfg.EDGE_TIMEOUT_SECONDS
                    self._stage(job,"speech")
                    self.speech_pool.submit(self._speak,job)
                else:
                    self._stage(job,"complete")
        except Exception as error:
            with self.condition:
                job.error_code = getattr(error,"code",None) or (str(error) if str(error) in
                    {"no_speech","conversation_expired"} else "storage_busy" if __import__('sqlite3').OperationalError == type(error)
                    else "invalid_audio" if isinstance(error,ValueError) and job.recording else "turn_failed")
                job.recording = None
                job.stage = "cancelled" if job.cancelled.is_set() else "failed"

    def _speak(self, job):
        from assistant.operations import Operation, operation_context, check
        started = monotonic()
        operation = Operation(job.session_id,job.turn_id,job.speech_deadline,cancelled=job.cancelled)
        try:
            with operation_context(operation):
                check()
                audio = speech.make_audio(job.result["answer_text"],job.result["language"],job.voice,
                    job.speed,provider=job.provider,allow_online=job.online_speech,
                    cacheable=job.result.get("response_status")=="answered")
                check()
                with self.condition:
                    job.result["audio"] = audio
        except Exception as error:
            with self.condition:
                job.result["audio_error"] = str(error) if isinstance(error,speech.SpeechError) else "Speech is unavailable; the reviewed answer remains available."
        finally:
            with self.condition:
                job.result["speech_seconds"] = monotonic()-started
                job.timings["audio_ready_seconds"] = monotonic()-job.submitted
                job.stage = "cancelled" if job.cancelled.is_set() else "complete"

    def retry_audio(self, session_id, turn_id, voice, speed, allow_online):
        """Reuse verified text and the original provider without re-entering the graph."""
        with self.condition:
            job = self.jobs[(session_id,turn_id)]
            if job.stage not in TERMINAL or not job.result.get("answer_text"):
                raise ValueError("conversation_busy")
            job.voice,job.speed,job.online_speech = voice,speed,allow_online
            job.cancelled = Event()
            job.result.update(audio=None,audio_error=None)
            job.stage = "speech"
            job.speech_deadline = monotonic()+cfg.EDGE_TIMEOUT_SECONDS
            self.speech_pool.submit(self._speak,job)

    def retry(self, session_id, turn_id, recording=None):
        """Preserve the original submission identity even if sidebar settings changed."""
        with self.condition:
            job = self.jobs[(session_id,turn_id)]
            return self.submit(session_id,turn_id,"" if turn_id.startswith("recording:") else job.question,
                job.profile,job.provider,job.voice,job.speed,job.spoken,job.online_speech,
                recording,job.input_language)

    def stats(self):
        """Cumulative counters plus live concurrency gauges (FutureWork 10 §7).

        Gauges are prefixed `gauge:` so a scrape can split them from the monotonic counters.
        They carry no student content — only queue depths and coarse stage counts.
        """
        with self.condition:
            snapshot = dict(self.counters)
            active = [j for j in self.jobs.values() if j.stage not in TERMINAL]
            snapshot["gauge:queue_depth"] = len(self.queue)
            snapshot["gauge:priority_depth"] = len(self.priority)
            snapshot["gauge:queue_depth_total"] = len(self.queue) + len(self.priority)
            snapshot["gauge:active_jobs"] = len(active)
            snapshot["gauge:queue_capacity"] = cfg.QUEUE_CAPACITY + 1
            snapshot["gauge:executing"] = sum(j.stage in {"transcribing", "reasoning", "speech"} for j in active)
            # Overload rate over all admission attempts that reached a capacity/deadline check.
            admitted = snapshot.get("admitted:short", 0) + snapshot.get("admitted:normal", 0)
            shed = snapshot.get("overload", 0) + snapshot.get("overload_predicted", 0)
            offered = admitted + shed
            snapshot["gauge:overload_rate"] = round(shed / offered, 4) if offered else 0.0
            return snapshot

    def close(self):
        """Drain test/operator-owned workers without leaving speech futures behind."""
        with self.condition:
            self.closed = True
            for job in self.jobs.values():
                job.cancelled.set()
            self.condition.notify_all()
        if self.worker.is_alive():
            self.worker.join(timeout=2)
        self.speech_pool.shutdown(wait=False,cancel_futures=True)
        # Keep the interprocess gate if a non-preemptible native job is still draining.
        if not self.worker.is_alive() and all(j.stage in TERMINAL for j in self.jobs.values()):
            self.runtime_lock.close()

    def _maintenance(self):
        while not self.closed:
            try:
                with self.condition:
                    active = {j.session_id for j in self.jobs.values() if j.stage not in TERMINAL}
                    self.store.maintain(active)
                    retained = self.store.session_ids()
                    for key in list(self.jobs):
                        if key[0] not in retained and key[0] not in active:
                            del self.jobs[key]
            except Exception as error:
                with self.condition:
                    self.counters["maintenance:"+type(error).__name__] += 1
            with self.condition:
                self.condition.wait_for(lambda:self.closed, timeout=cfg.MAINTENANCE_SECONDS)


@lru_cache(maxsize=1)
def manager():
    """Initialize the sibling import boundary once before starting owned workers."""
    import sys
    cfg.configure_agent()
    if str(cfg.AGENT_ROOT) not in sys.path:
        sys.path.insert(0,str(cfg.AGENT_ROOT))
    return JobManager()
