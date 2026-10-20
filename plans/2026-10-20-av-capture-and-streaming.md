# Audio/Video Capture, Streaming and the External Control API — Design Notes

- **Date:** 2026-10-20
- **Status:** Design notes (not yet a spec). Captures the user's direction and the decisions made in
  conversation so a later brainstorm → spec → plan can start from them.
- **Builds on:** the gameplay replay work (`plans/2026-10-19-gameplay-replay.md`, its master plan and
  sub-plans) — see "What we reuse" below.
- **Listed in:** `plans/future-work.md` ("Headless capture to raw files and a frame/audio ready latch").

## Goals (user direction)

1. Capture the game's picture and sound from a headless run, fast, without touching the disk.
2. Stream audio/video **losslessly** to consumers: an AI that needs real screenshots and sound,
   Twitch-style broadcasting, spectators, remote multiplayer.
3. A separate **event/state stream** API (sprite state, events, game state, input injection), which
   may be lossy.
4. Performance is the top priority; avoid disk writes; use the fastest transport each platform offers.
5. Reuse and commoditize the replay engine's design wherever it makes sense.

## Two APIs, two kinds of data

| | A/V stream | Event/state stream |
|---|---|---|
| Content | raw pixels (RGBA) and PCM audio (44100 Hz, signed 16-bit, stereo) | per-frame sprite sample (the trace sample), events, declared game state, input |
| Volume | large: a 640×480 frame is ~1.2 MB raw (~74 MB/s at 60 FPS); audio ~176 KB/s | small |
| Encoding | binary: fixed header + payload; lossless codec | JSON (the trace record shapes), optionally compressed |
| Fidelity | **lossless codec AND lossless delivery** — every frame, bit-exact | lossless or lossy (latest-wins), chosen per consumer |
| Transports | reliable only (shared memory, Unix socket, named pipe, TCP) | any, including UDP |

JSON/gzip (the trace format) is right for recordings and state but far too slow for raw frames, so
the A/V stream never uses it.

## The frame packet and the latch

- **One latch per frame** (decided): each frame is a packet = the presented picture + exactly the
  audio that plays during that frame (sample count from that frame's duration, ~735 stereo samples
  at 60 FPS, carrying the fractional sample forward). The engine sets the latch to 1 when the packet
  is written; the consumer reads it and writes 0.
- **Lockstep mode**: the engine waits for the 0 before producing the next frame — deterministic and
  complete. Requires the engine to render each frame's audio slice itself (an offline, per-frame
  mixing path): pygame's mixer runs on its own real-time thread even with the dummy driver, so it
  cannot simply be tapped while the engine waits. The synth/live-voice code already generates
  samples; sounds played through `pygame.mixer` need the offline path. **This is the main design
  question.**
- **Free-running mode**: the engine never waits; the latch covers frames only (latest frame wins);
  audio is a continuous stream in a ring buffer the consumer reads at its own pace.
- Lockstep is allowed only on lossless transports; requesting it on a lossy one is refused with
  `ExitCode.OPTIONS_REFUSED`.

## Packet format (A/V)

- Fixed little-endian header: magic, format version, frame number, packet kind (video / audio /
  combined), width, height, pixel format, sample rate/channels/sample format, payload length, codec
  id, keyframe flag.
- Payload: raw bytes or codec output.
- **Keyframes and deltas, reusing the trace idea**: a keyframe carries the whole frame; a delta
  carries the frame XOR the previous frame (pixel art is mostly static, so deltas compress
  dramatically) — lossless. A consumer that joins mid-stream waits for the next keyframe; keyframes
  every N frames (and on scene change, as traces do).
- **Codecs (lossless only, pluggable)**: none (raw, fastest locally), LZ4 (very fast), zstd at a low
  level (better ratio); later video-specific lossless (QOI per frame, FFV1) and FLAC for audio.
  Never gzip (too slow).

## Transports (one sink interface, platform-specific backends)

| Transport | Speed | Platforms | Lossless delivery | Notes |
|---|---|---|---|---|
| Shared-memory ring buffer | fastest, zero copy | all (`multiprocessing.shared_memory`, incl. Windows) | yes | latch in the segment header; 2–3 slots so writing and reading overlap |
| Unix domain socket | very fast | macOS, Linux (Windows partial) | yes | simple local streaming |
| Windows named pipe | very fast | Windows | yes | Windows counterpart of a Unix socket |
| TCP | network | all | yes | remote consumers, Twitch, multiplayer |
| UDP | network, lowest latency | all | no | event/state stream only; frames fragmented with sequence numbers, a frame with any lost fragment is dropped whole (never torn) |
| RAM-disk file | fast | Linux `/dev/shm`; no built-in on macOS/Windows | yes | fallback; shared memory is better everywhere |

Performance details: copy pixels straight from the display surface's buffer into the shared-memory
slot (no per-frame allocation); downscale or skip frames before the copy, not after; the sink runs
on the engine's thread with bounded work per frame, or hands off to a writer thread with a bounded
queue (never unbounded memory growth).

## `--headless DIR` (simplest consumer)

Writes `video.raw` (+ a sidecar describing width, height, pixel format, frame count; pipe-able to
`ffmpeg -f rawvideo`) and `audio.raw` (the mix, PCM). It is the file-sink backend of the same sink
interface, useful for debugging and offline encoding; the streaming transports are the primary path.

## External control API (event/state stream) — brainstorm

- **Observe**: raw pixels (via the A/V stream); sprite state as data (the trace sample); declared
  game state (score, lives, level — the same named fields a future cheat device needs); audio
  buffer and which sounds/voices started this frame; frame hashes for desync detection.
- **Act**: input injection through the doors as an "external input" source (alongside live and
  replay); scripted supervisor actions at the existing hook; time control (pause, step N, speed,
  reset with a seed); save/load state (needs state snapshots); scene control.
- **Output**: draw pixels/lines/rects/text/sprites to an overlay layer (never in traces unless
  asked); play a voice from a waveform equation or preset with duration, pitch curve and envelope
  (synth toolkit / live voices); speech (TTS); rumble/LED.
- **Recording**: start/stop `--record-trace`, fetch a recording, replay it, `--audit` it.
- **Shape**: a Gymnasium-style environment wrapper — `reset(seed)`, `step(actions)` →
  `(observation, reward, done, info)` — on lockstep + seeded doors; transports as above (check what
  `glitchygames/api/` server/client already provide).
- **Security**: authentication for remote input, rate limits, a read-only spectator mode.

## What we reuse from the replay engine (and commoditize)

- **The doors pattern, mirrored for outputs**: replay added swappable *sources* (input side). The
  A/V tap adds swappable *sinks* (output side) with the same rules — one interface, live providers
  by default, installed before the first frame, no mixing mid-run, a guard test against bypassing.
- **Framed-stream layer (commoditize)**: header + numbered per-frame records + keyframe/delta
  encoding + pluggable codec + pluggable transport. Today `glitchygames/tracing.py` does a JSON/gzip
  version of exactly this; factor the shared part out so traces (JSON lines, gzip, file) and A/V
  (binary, LZ4/zstd, shared memory/sockets) are two configurations of one layer.
- **Exactness and the frame clock**: packets are stamped with the frame number and frame-clock time
  (not wall clock), so a replay rendered to A/V is bit-identical every time — perfect bug-report
  videos from any recording.
- **Headless mode** (`--headless`, dummy SDL drivers, replays unpaced) as the host for capture.
- **Supervisor hook and control events** as the attachment point for API actions, recorded so an
  API-driven session still replays exactly.
- **The input-blocking helper** (`glitchygames/replay/input_blocking.py`) for API "take over" and for
  keeping real input out while an external source drives the game.
- **`--audit`** to check that a stream's producer is deterministic.
- **`ExitCode`** members for every refusal and failure; version fields in every header; refusals of
  unknown versions.
- **Golden fixtures**: golden A/V captures of the golden replays, compared bit-for-bit.

## Where it leads (later epics)

- AI players and testers: lockstep A/V + state in, input injection out; every run recorded,
  replayable and auditable.
- Twitch Plays: chat commands → input (voting/anarchy, per-viewer cooldown); stream from the A/V
  stream via ffmpeg.
- Remote multiplayer: lockstep input sync from the deterministic doors, verified with frame hashes;
  rollback netcode needs state snapshots (the shared prerequisite with fast step-back and long
  instant replays).
- Spectating: stream recorded inputs (tiny) and replay them on the viewer's machine, or stream A/V.

## Open questions for the brainstorm

1. Offline per-frame audio rendering: how to mix `pygame.mixer` sounds offline (own mixer for
   capture runs, or synth-only audio in lockstep).
2. Whether the framed-stream refactor of `tracing.py` lands first or alongside the A/V work.
3. Default codec per transport (raw for shared memory, zstd for TCP?) and keyframe interval.
4. Whether the event/state API and the existing `glitchygames/api/` server merge or stay separate.
