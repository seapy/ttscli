# ttscli

A CLI tool for converting [sttcli](https://github.com/seapy/sttcli) transcripts to audio using multiple TTS providers. Supports timed mode (fits speech within original segment timestamps) and natural mode (unconstrained pacing).

## Installation

```bash
uv tool install git+https://github.com/seapy/ttscli.git
```

ffmpeg is required for audio assembly and time-stretching:
```bash
brew install ffmpeg        # macOS
sudo apt install ffmpeg    # Ubuntu/Debian
```

## API Keys

Create `~/.ttscli.toml` and add keys for the providers you want to use:

```toml
[elevenlabs]
api_key = "sk_..."
default_voice_id = "JBFqnCBsd6RMkjVDRZzb"

[gemini]
api_key = "AIza..."
default_voice = "Kore"

[minimax]
api_key = "..."
group_id = "..."
default_voice = "male-qn-qingse"

[speakers]
# Map speaker labels to voice IDs (provider-agnostic)
speaker_0 = "JBFqnCBsd6RMkjVDRZzb"
speaker_1 = "EXAVITQu4vr4xnSDxMaL"
```

Environment variables are also supported: `ELEVENLABS_API_KEY`, `GEMINI_API_KEY`, `MINIMAX_API_KEY`, `MINIMAX_GROUP_ID`.

## Usage

```bash
ttscli convert transcript.md
ttscli convert transcript.md -o output.mp3 --provider elevenlabs
```

Input must be a markdown transcript produced by `sttcli`.

### Providers

| Provider | Default model | Speed param | Speed range | Notes |
|---|---|---|---|---|
| `elevenlabs` | eleven_multilingual_v2 | ❌ (ffmpeg) | — | Rich voice library, fastest |
| `gemini` | gemini-2.5-flash-preview-tts | ❌ (ffmpeg) | — | High quality, slower per segment |
| `minimax` | speech-01-turbo | ✅ | 0.5–2.0× | Korean/Chinese optimized |

```bash
ttscli convert transcript.md --provider elevenlabs
ttscli convert transcript.md --provider gemini
ttscli convert transcript.md --provider minimax
```

### Modes

**timed** (default) — each segment's audio is stretched to fit within its original timestamp window:
```bash
ttscli convert transcript.md --mode timed
```

**natural** — speech is synthesized at its natural pace and concatenated sequentially:
```bash
ttscli convert transcript.md --mode natural
```

### Gender-based voice selection

When the input transcript contains gender metadata (produced by sttcli), ttscli automatically selects a gender-appropriate voice for each segment. No configuration is required.

| Provider | male (default) | female (default) |
|---|---|---|
| `elevenlabs` | Antoni (`ErXwobaYiN019PkySvjV`) | Rachel (`21m00Tcm4TlvDq8ikWAM`) |
| `gemini` | Charon | Kore |
| `minimax` | `male-qn-qingse` | `female-shaonv` |

To override the gender-default voices, add `male_voice` / `female_voice` to `~/.ttscli.toml`:

```toml
[elevenlabs]
male_voice = "TxGEqnHWrfWFTfGW9XjX"
female_voice = "EXAVITQu4vr4xnSDxMaL"

[gemini]
male_voice = "Fenrir"
female_voice = "Aoede"

[minimax]
male_voice = "male-qn-jingying"
female_voice = "female-yujie"
```

Voice selection priority (highest to lowest):
1. `--speaker-voice SPEAKER=VOICE` or config `[speakers]`
2. `--voice` or config `default_voice`
3. Gender-based default (from transcript metadata)
4. First available voice from provider

### Speaker voice mapping

Assign different voices per speaker:
```bash
ttscli convert transcript.md --provider elevenlabs \
  --speaker-voice speaker_0=JBFqnCBsd6RMkjVDRZzb \
  --speaker-voice speaker_1=EXAVITQu4vr4xnSDxMaL
```

Convert only a specific speaker:
```bash
ttscli convert transcript.md --provider elevenlabs \
  --speaker speaker_0 \
  --voice JBFqnCBsd6RMkjVDRZzb
```

### List available voices

```bash
ttscli voices --provider elevenlabs
ttscli voices --provider gemini
ttscli voices --provider minimax
```

### Speed range (timed mode)

Control how aggressively speech is sped up or slowed down to fit the timestamp window:
```bash
ttscli convert transcript.md --speed-range 0.5,2.0   # wider range
ttscli convert transcript.md --speed-range 0.9,1.1   # tighter, more warnings
```

Segments that fall outside the range are clamped and logged as warnings.

### Save to file

```bash
ttscli convert transcript.md -o output.mp3
ttscli convert transcript.md -o output.wav --format wav
```

Default output path: `<input>_tts.mp3`

## Reference

### `ttscli convert`

```
ttscli convert <INPUT_FILE> [OPTIONS]

  -p, --provider [elevenlabs|gemini|minimax]   TTS provider (default: elevenlabs)
  -o, --output PATH                            Output file (default: <input>_tts.mp3)
      --mode [timed|natural]                   Timing mode (default: timed)
  -m, --model TEXT                             Model name override
      --voice TEXT                             Default voice ID/name
      --voice-id TEXT                          Voice ID alias (ElevenLabs)
      --speaker-voice SPEAKER=VOICE            Per-speaker voice mapping (repeatable)
      --speaker TEXT                           Only convert this speaker (repeatable)
      --format [mp3|wav]                       Output format (default: mp3)
      --speed-range TEXT                       Speed range min,max (default: 0.75,1.4)
      --stability FLOAT                        ElevenLabs stability 0.0–1.0
      --minimax-group-id TEXT                  MiniMax group ID
      --api-key TEXT                           API key override
      --config PATH                            Config file (default: ~/.ttscli.toml)
```

### `ttscli voices`

```
ttscli voices [OPTIONS]

  -p, --provider [elevenlabs|gemini|minimax]   TTS provider (default: elevenlabs)
      --api-key TEXT                           API key override
      --config PATH                            Config file (default: ~/.ttscli.toml)
```
