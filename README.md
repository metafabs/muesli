# Muesli

**Muesli** is a local-first meeting notes tool for macOS. It records microphone audio, transcribes it locally with `faster-whisper`, summarizes it locally through Ollama, and writes a structured Markdown note into an Obsidian vault.

The core goal is simple: stay present in the meeting, then let the machine handle capture, transcription, and note formatting without sending meeting audio or transcripts to a cloud transcription service.

## What it does

```text
meeting
→ temporary local audio chunks
→ local transcription with faster-whisper
→ local summary with Ollama
→ Markdown note in Obsidian
→ temporary audio cleanup after a normal run
```

Current output includes:

- TLDR
- Discussion Summary
- Key Points
- Decisions
- Action Items
- Open Questions
- Full transcript

Muesli also preserves the transcript if summarization fails, so the latest failed note can be summarized again without recording or transcribing the meeting a second time.

## Local-first behavior

Muesli is designed so that the sensitive meeting content stays on your machine:

- Audio is recorded locally.
- Transcription runs locally with `faster-whisper`.
- Summarization runs against a local Ollama instance at `localhost`.
- Notes are written directly to a local Obsidian folder.
- Your personal config file is local-only and excluded from Git.
- Temporary audio chunks are deleted after a normal processing run.

If the process is interrupted or crashes before cleanup, temporary chunks can remain in `temp_audio/`. They are ignored by Git and can be deleted manually.

## Requirements

- macOS
- Python 3
- Ollama
- A local Ollama model such as `gemma4:12b`
- PortAudio-compatible microphone input
- Obsidian, or any local folder where you want the Markdown notes written

## Install

Clone the repository:

```bash
git clone https://github.com/metafabs/muesli.git
cd muesli
```

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Install Ollama and a local model

Install Ollama, then pull a model for meeting summaries:

```bash
ollama pull gemma4:12b
```

Confirm it is available:

```bash
ollama list
```

On Apple Silicon, you can use an MLX-optimized model if you already have one available in Ollama. Set the model name in your local config accordingly.

## Configure Muesli

Copy the example config:

```bash
cp muesli_config.example.yaml muesli_config.yaml
```

`muesli_config.yaml` is intentionally ignored by Git. Put machine-specific paths and local preferences there, not in the tracked example file.

At minimum, set the folder where Muesli should write meeting notes:

```yaml
obsidian:
  meetings_folder: "/path/to/your/obsidian/vault/meetings"
```

A typical config looks like this:

```yaml
models:
  meeting_summary: "gemma4:12b"

transcription:
  whisper_model: "base"
  language: null
  device: "cpu"
  compute_type: "int8"

obsidian:
  meetings_folder: "/path/to/your/obsidian/vault/meetings"

audio:
  chunk_seconds: 45
  delete_temp_audio: true

summary:
  temperature: 0.2
```

With `language: null`, Whisper detects the transcription language automatically. You can instead set a language code if you want to force a specific language.

## Run it

From the project folder:

```bash
python muesli_meeting.py
```

Muesli will ask for a meeting name, then:

```text
Press Enter to start recording...
Press Enter to stop recording...
```

After recording stops, it transcribes, summarizes, writes the note, and cleans up the temporary audio chunks.

## Optional `muesli` terminal command

If you want to launch it by typing `muesli`, create a wrapper:

```bash
mkdir -p ~/bin

cat > ~/bin/muesli <<'WRAPPER'
#!/bin/zsh
cd "$HOME/muesli" || exit 1
exec "$HOME/muesli/.venv/bin/python" "$HOME/muesli/muesli_meeting.py" "$@"
WRAPPER

chmod +x ~/bin/muesli
```

Make sure `~/bin` is on your `PATH`:

```bash
grep -qxF 'export PATH="$HOME/bin:$PATH"' ~/.zshrc || echo 'export PATH="$HOME/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

Then run:

```bash
muesli
```

## Re-summarize the latest failed note

If transcription succeeded but Ollama failed during summarization, the transcript is preserved in the Obsidian note.

Retry the latest failed note with:

```bash
muesli --resummarize-latest
```

This does not re-record or re-transcribe the meeting. It reuses the transcript already saved in the note.

## Output format

Muesli writes Markdown notes with YAML frontmatter:

```markdown
---
type: meeting
source: muesli
date: YYYY-MM-DD
meeting: Meeting Name
audio_saved: false
status: complete
tags:
  - meeting
---

# YYYY-MM-DD - Meeting Name

## TLDR

## Discussion Summary

## Key Points

## Decisions

## Action Items

## Open Questions

## Transcript
```

If summarization fails, the note is marked `status: summary_failed` and the transcript remains available for recovery.

## Audio limitations

The current version records from the default microphone input.

That works well for in-person conversations or calls where the other side is audible through speakers. If you use headphones during Zoom, Meet, Teams, or another call, the microphone may not capture the other participant clearly.

Capturing system audio requires a separate audio-routing setup such as BlackHole or Loopback and is not built into Muesli itself.

## Privacy and recording notice

Muesli is a local tool, but recording laws and workplace policies still apply. Make sure participants are informed and that you have permission to record where required.

Do not commit your real `muesli_config.yaml`, meeting notes, transcripts, audio chunks, `.env` files, or local backup files to the repository.

## Status

Muesli is an early personal project. The core capture → transcribe → summarize → Obsidian workflow works, but it is not packaged as a polished desktop application and has not been tested across every Mac or Ollama configuration.

## License

No open-source license has been selected yet. Until one is added, the repository is source-available for viewing but no additional permissions are granted by default.
