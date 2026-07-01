# Muesli

**Muesli** is a local-first meeting notes tool that records a meeting, transcribes it locally, summarizes it locally, and writes a clean Markdown note into an Obsidian vault.

It is designed for people who want useful meeting notes without sending audio, transcripts, or summaries to cloud services.

## What it does

```text
meeting happens
→ temporary audio is captured locally
→ transcript is generated locally with faster-whisper
→ TLDR / key points / decisions / action items are generated locally with Ollama
→ a Markdown note is written to Obsidian
→ temporary audio is deleted
```

## Current version

Muesli is an early local prototype, but the core flow works.

Today it supports:

- Terminal command: `muesli`
- Mic recording through PortAudio / `sounddevice`
- Chunked temporary audio recording for longer meetings
- Local transcription with `faster-whisper`
- Local summarization through Ollama
- Markdown note creation in Obsidian
- Temporary audio cleanup after processing

## Local-first principles

Muesli is built around a few constraints:

- No cloud transcription
- No cloud summarization
- No permanent audio storage
- Transcript saved locally
- Summary generated locally
- Markdown written directly to Obsidian

## Requirements

- macOS
- Python 3
- Ollama
- `gemma4:12b` pulled in Ollama
- PortAudio-compatible audio input
- Obsidian vault folder

Python packages used:

- `faster-whisper`
- `sounddevice`
- `scipy`
- `numpy`
- `pyyaml`
- `requests`

## Install

Clone the repo:

```bash
git clone https://github.com/metafabs/muesli.git
cd muesli
```

Create a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Copy the example config:

```bash
cp muesli_config.example.yaml muesli_config.yaml
```

Edit `muesli_config.yaml` and set your Obsidian meetings folder:

```yaml
obsidian:
  meetings_folder: "/path/to/your/obsidian/vault/meetings"
```

## Ollama setup

Install Ollama, then pull the meeting summary model:

```bash
ollama pull gemma4:12b
```

Check that the model is available:

```bash
ollama list
```

## Create the terminal command

Create a small wrapper so you can run Muesli by typing `muesli`:

```bash
mkdir -p ~/bin

cat > ~/bin/muesli <<'WRAPPER'
#!/bin/zsh
cd "$HOME/muesli" || exit 1
exec "$HOME/muesli/.venv/bin/python" "$HOME/muesli/muesli_meeting.py"
WRAPPER

chmod +x ~/bin/muesli
```

Make sure `~/bin` is in your path:

```bash
grep -qxF 'export PATH="$HOME/bin:$PATH"' ~/.zshrc || echo 'export PATH="$HOME/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

Then run:

```bash
muesli
```

## Usage

```text
Meeting name:
Press Enter to start recording.
Press Enter to stop recording.
Transcribing...
Summarizing...
Saved to Obsidian.
```

## Output format

Muesli writes notes using this structure:

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

## Current model choice

Muesli currently uses:

```yaml
models:
  meeting_summary: "gemma4:12b"
```

This was chosen because it runs locally through Ollama and gives stronger meeting summaries than the smaller models tested so far.

## Notes on audio

The current version records from the default microphone input and writes temporary audio in chunks.

If you are on headphones during a Zoom / Meet / Teams call, mic-only capture may not hear the other person clearly. Capturing guest/system audio requires an additional routing layer such as BlackHole or Loopback.

## Recording notice

Make sure everyone in a meeting is aware before recording.

## License

Private prototype for now. License to be decided before public release.

### Apple Silicon optimization

By default, Muesli uses a portable Ollama model name:

```yaml
meeting_summary: "gemma4:12b"
```

On Apple Silicon Macs, you can try the MLX-optimized version for faster local summarization:

```yaml
meeting_summary: "gemma4:12b-mlx"
```

Pull it first:

```bash
ollama pull gemma4:12b-mlx
```

Keep this setting in your local `muesli_config.yaml`. The example config stays portable for users on different machines.
