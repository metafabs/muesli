# Muesli

**Muesli** is a local-first meeting notes tool for macOS. It records microphone audio, transcribes it locally with `faster-whisper`, summarizes it locally through Ollama, and writes a structured Markdown note into an Obsidian vault or any normal folder.

The core goal is simple: stay present in the meeting, then let the machine handle capture, transcription, and note formatting without sending meeting audio or transcripts to a cloud transcription service.

## Beginner installation

You do **not** need to be a programmer to try Muesli. You do need a Mac and about 10–20 minutes for the first setup. The first model download can take longer depending on your internet connection.

### 1. Open Terminal

On your Mac, press `Command + Space`, type `Terminal`, and open it.

### 2. Install Homebrew if you do not already have it

Paste this into Terminal:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Follow the instructions Homebrew shows you.

### 3. Download Muesli

Paste these commands into Terminal:

```bash
git clone https://github.com/metafabs/muesli.git
cd muesli
```

### 4. Run the setup assistant

```bash
zsh setup.sh
```

The setup script will:

- check the Mac requirements
- install Python if needed
- install PortAudio
- install Ollama if needed
- create a private Python environment for Muesli
- install the Python packages
- ask where you want meeting notes saved
- download the local summary model if needed
- create a `muesli` Terminal command

If you already have a personal `muesli_config.yaml`, setup leaves it unchanged.

### 5. Choose where notes should go

When setup asks where to save meetings, you have two easy options.

**Recommended: Obsidian.** Install Obsidian, create or open a vault, then give Muesli a folder inside that vault. For example:

```text
/Users/yourname/Documents/My Vault/Meetings
```

**No Obsidian? No problem.** Press Enter and Muesli will use:

```text
~/Documents/Muesli Meetings
```

Muesli writes normal Markdown files, so Obsidian is useful but not required.

### 6. Start Muesli

Open a new Terminal window and run:

```bash
muesli
```

Muesli asks for a meeting name. Press Enter to start recording and Enter again to stop.

The first transcription can take longer because the Whisper model may need to download once.

### If you get stuck

You can paste this GitHub repository link into ChatGPT and say:

> I am not a programmer. Help me install this Muesli project on my Mac one step at a time. Check that each step worked before giving me the next one.

That is a good fallback for machine-specific Homebrew, Python, microphone-permission, or Ollama issues.

## What it does

```text
meeting
→ temporary local audio chunks
→ local transcription with faster-whisper
→ local summary with Ollama
→ Markdown note in Obsidian or another local folder
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

Muesli is designed so that sensitive meeting content stays on your machine:

- Audio is recorded locally.
- Transcription runs locally with `faster-whisper`.
- Summarization runs against a local Ollama instance at `localhost`.
- Notes are written directly to a local folder.
- Your personal config file is local-only and excluded from Git.
- Temporary audio chunks are deleted after a normal processing run.

If the process is interrupted or crashes before cleanup, temporary chunks can remain in `temp_audio/`. They are ignored by Git and can be deleted manually.

## Requirements

- macOS
- Python 3
- Ollama
- A local Ollama model such as `gemma4:12b`
- PortAudio-compatible microphone input
- Obsidian or any local folder where you want the Markdown notes written

The beginner setup script handles most of this automatically after Homebrew is installed.

## Manual installation

If you prefer to set Muesli up yourself, clone the repository:

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

Install Ollama and pull a model for meeting summaries:

```bash
ollama pull gemma4:12b
```

Confirm it is available:

```bash
ollama list
```

Copy the example config:

```bash
cp muesli_config.example.yaml muesli_config.yaml
```

`muesli_config.yaml` is intentionally ignored by Git. Put machine-specific paths and local preferences there, not in the tracked example file.

At minimum, set the folder where Muesli should write meeting notes:

```yaml
obsidian:
  meetings_folder: "/path/to/your/notes/folder"
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
  meetings_folder: "/path/to/your/notes/folder"

audio:
  chunk_seconds: 45
  delete_temp_audio: true

summary:
  temperature: 0.2
```

With `language: null`, Whisper detects the transcription language automatically. You can instead set a language code if you want to force a specific language.

On Apple Silicon, you can use an MLX-optimized Ollama model if you already have one available. Set the model name in your local config accordingly.

## Run it manually

From the project folder with the virtual environment active:

```bash
python muesli_meeting.py
```

## Re-summarize the latest failed note

If transcription succeeded but Ollama failed during summarization, the transcript is preserved in the note.

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

Muesli is an early personal project. The core capture → transcribe → summarize → Markdown workflow works, but it is not packaged as a polished desktop application and has not been tested across every Mac or Ollama configuration.

## License

Muesli is released under the MIT License. See `LICENSE` for details.
