# Rime Text-to-Speech & Version-Safe Audio Pipeline — Phase 4 Evidence

## 1. Executive Summary

Phase 4 integrates text-to-speech output powered by the **Rime Speech Engine** (`mist` model, `amber` voice) into the **VoiceForm** architecture. The speech pipeline is engineered around the core system invariant:

> **"Cancellation improves efficiency, but version fencing guarantees correctness."**

Under this invariant:
- Network or compute cancellation aborts obsolete TTS tasks early to save compute and network resources.
- If a slow, delayed, or uncancellable TTS synthesis completes after the user has interrupted or changed fields, **version fencing guarantees the user never hears obsolete audio**.

---

## 2. The 5-Checkpoint Version Defense Architecture

To ensure zero speech leakage, audio synthesis and playback pass through 5 sequential verification checkpoints:

```
+-----------------------------------------------------------------------------------+
|                           5-CHECKPOINT DEFENSE IN ACTION                          |
+-----------------------------------------------------------------------------------+
 1. Accepted Assistant Response (v10)
    ↓
 [ CHECKPOINT 1: Backend Pre-Dispatch Guard ]
    - Verifies: interaction_version == active_version
    - Action if Stale: Aborts before making HTTP request to Rime API
    ↓
 2. Rime TTS Synthesis Initiated (Background Task in TaskManager)
    ↓
 [ CHECKPOINT 2: Backend Task Invalidation on Interruption ]
    - Action on New User Voice Input (v11): InteractionVersionManager advances active_version to 11
    - TaskManager signals asyncio cancellation on in-flight v10 TTS task
    ↓
 3. Rime API Response Received
    ↓
 [ CHECKPOINT 3: Backend Stale Result Guard ]
    - Verifies: interaction_version (10) == active_version (11)
    - Action if Stale: Discards audio payload, records `TTS_RESULT_BLOCKED_STALE`, suppresses event emission
    ↓
 4. WebSocket Payload Dispatched (if valid)
    ↓
 [ CHECKPOINT 4: Frontend Enqueue Guard ]
    - Verifies: payload.interaction_version == playbackManager.activeVersion
    - Action if Stale: Rejects audio from entering the playback queue, sets status to `BLOCKED_STALE`
    ↓
 5. Playback Queue Dequeue
    ↓
 [ CHECKPOINT 5: Immediate Pre-Playback Guard ]
    - Verifies: item.interaction_version == playbackManager.activeVersion immediately before calling `audio.play()`
    - Action if Stale: Discards item, triggers next queued item, prevents speaker activation
    ↓
 6. Active Audio Output (Browser Speaker)
    - If user interrupts while playing: `audioPlaybackManager.stopCurrentAudio()` executes synchronously, clearing speaker output and queue.
```

---

## 3. Real Rime Configuration (Single Source of Truth)

All components reference environment variables as the single source of truth:

| Configuration Parameter | Environment Variable | Default Value | Description |
|---|---|---|---|
| **API Key** | `RIME_API_KEY` | `""` (Empty string) | Secret server-side token; never sent to browser |
| **Model** | `RIME_MODEL` | `"mist"` | Ultra-low latency conversational speech model |
| **Voice** | `RIME_VOICE` | `"amber"` | Conversational voice persona |
| **Endpoint** | `RIME_ENDPOINT` | `"https://users.rime.ai/v1/rime-tts"` | Rime REST synthesis endpoint |
| **Audio Format** | `Accept: audio/mp3` | `"audio/mp3"` | Standard MP3 audio returned by Rime API |
| **Transport** | HTTP POST | `httpx.AsyncClient` | JSON payload `{"text", "speaker", "modelId"}` |

### System Alignment Across Layers
- **Backend Core:** `backend/app/core/config.py` loads `RIME_API_KEY`, `RIME_MODEL`, `RIME_VOICE`, `RIME_ENDPOINT`.
- **RimeProvider:** `backend/app/services/speech_provider.py` passes `model` and `speaker` in request payload and returns `audio/mp3`.
- **API Status Endpoint:** `GET /api/speech/status` returns `provider_name`, `is_fallback`, `rime_configured`, `model`, `voice`, and `endpoint`.
- **Frontend UI:** `SpeechStatusPanel.tsx` and `App.tsx` dynamically display the active configuration returned by the backend and distinguish **Rime Active**, **Mock Active**, **Rime Configured**, **Rime Not Configured**, and **Fallback Active**.
- **Configuration Spec:** `.env.example` documents all 4 variables with matching defaults.

---

## 4. Test Strategy: Real Integration vs. Deterministic Mock Tests

To maintain scientific rigor, tests are strictly categorized into two types:

### A. Real Rime Live Integration Smoke Test (`backend/tests/manual_rime_smoke_test.py` & `backend/tests/test_rime_integration.py`)
- **Objective:** Verifies actual network connectivity, authentication, response headers, and audio binary payload with the external Rime REST API.
- **Execution Condition:** Runs only when `RIME_API_KEY` is present.
- **Smoke Test Procedure:**
  ```bash
  export RIME_API_KEY="your_actual_api_key"
  python backend/tests/manual_rime_smoke_test.py
  ```
- **Output Structure:**
  ```text
  RIME_SMOKE_TEST_SUCCESS
  Model: mist
  Voice: amber
  Endpoint: https://users.rime.ai/v1/rime-tts
  Audio bytes: <actual_byte_count>
  Format: audio/mp3
  Interaction Version Tag: 101
  ```
  *(API keys are never logged or exposed).*

### B. Deterministic Architectural Unit & Race Tests (`backend/tests/test_speech_pipeline.py`)
- **Objective:** Verifies state machine correctness, async version monotonicity, task cancellation, and 5-checkpoint stale audio suppression under reproducible race conditions.
- **Provider Used:** `MockSpeechProvider` with configurable artificial delays and valid PCM WAV audio headers.
- **Scenarios Verified:**

| Test # | Test Name | Invariant Verified | Result |
|---|---|---|---|
| 1 | `test_fresh_speech_result_accepted` | Audio generated for current active version passes Checkpoints 1-3 | **PASSED** |
| 2 | `test_stale_speech_generation_result_blocked` | Delayed TTS returning after version increment is intercepted at Checkpoint 3 | **PASSED** |
| 3 | `test_new_interaction_cancels_old_tts_task` | Invalidation listener triggers `TaskManager.cancel_tasks_for_version` | **PASSED** |
| 4 | `test_uncancellable_old_tts_task_cannot_enqueue_audio` | Uncancellable slow network streams are rejected by version comparison | **PASSED** |
| 5 | `test_audio_payload_rejected_at_checkpoint_1_if_already_stale` | Outdated requests are dropped before dispatching to provider | **PASSED** |
| 6 | `test_multiple_rapid_versions_leaves_only_latest_audio_valid` | Sequential requests (v30, v31, v32) leave only v32 eligible | **PASSED** |
| 7 | `test_tts_failure_does_not_corrupt_form_state` | External 503 error handled gracefully without corrupting form state | **PASSED** |
| 8 | `test_speech_lifecycle_events_contain_correct_versions` | Structured events in timeline contain monotonic interaction tags | **PASSED** |
| 9 | `test_conversation_service_triggers_speech_synthesis` | Natural language processing dispatches versioned speech synthesis | **PASSED** |
| 10 | `test_mode_a_interactive_scenario` | Mode A: v40 slow generation interrupted by v41 -> v40 blocked as stale, active=41 | **PASSED** |
| 11 | `test_mode_b_interactive_scenario` | Mode B: v50 playing interrupted by v51 -> playback stopped, active=51 | **PASSED** |
| 12 | `test_mode_c_interactive_scenario` | Mode C: v60, v61, v62 fired rapidly -> only v62 eligible for playback, active=62 | **PASSED** |

---

## 5. UI Provider Status States

The frontend UI dynamically reflects backend status without hardcoded fallback strings:

| Status Badge | Condition | Visual Indicator |
|---|---|---|
| **Rime Active** | `provider_name === 'Rime'` | Emerald badge with ShieldCheck |
| **Mock Active** | `provider_name.includes('Mock') && !is_fallback` | Indigo badge with Activity |
| **Mock Active (Fallback Active)** | `is_fallback === true` | Amber badge with Activity |
| **Rime Configured** | `rime_configured === true` | Emerald outline badge |
| **Rime Not Configured** | `rime_configured === false` | Neutral slate outline badge |

---

## 6. Known Limitations

1. **Rime API Dependency:** In environments without `RIME_API_KEY`, the application automatically defaults to `MockSpeechProvider` (Fallback Active). Real audio synthesis requires setting `RIME_API_KEY` in environment secrets.
2. **Network Jitter & Streaming:** Rime HTTP synthesis returns a complete MP3 buffer rather than chunked WebAudio stream. Version fences at Checkpoint 3 and Checkpoint 4 intercept late-arriving buffers cleanly.
3. **Browser Autoplay Policies:** Browser security requires an initial user interaction (click or keypress) before allowing programmatic audio playback. The `Play Test Response` and `Test Scenarios` buttons provide explicit user activation.
