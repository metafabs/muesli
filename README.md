# Muesli

**Muesli** is a local-first meeting notes tool that records a meeting, transcribes it locally, summarizes it locally, and writes a clean Markdown note into an Obsidian vault.

It is not an audio recorder. It is a small command-line tool for turning conversations into Obsidian-ready meeting notes.

## What it does

```text
meeting happens
→ temporary audio is captured locally
→ transcript is generated locally with faster-whisper
→ TLDR / key points / decisions / action items are generated locally with Ollama
→ a Markdown note is written to Obsidian
→ temporary audio is deleted
Current status

Muesli is currently an early local prototype.

Working:

Terminal command: muesli
Mic recording through PortAudio / sounddevice
Local transcription with faster-whisper
Local summarization through Ollama
Markdown note creation in Obsidian
Temporary audio cleanup

Not built yet:

System audio / guest audio capture
Chunked transcription during long meetings
Speaker diarization
Calendar integration
Hotkey
GUI
Local-first principles

Muesli is designed around a few constraints:

No cloud transcription
No cloud summarization
No permanent audio storage
Transcript saved locally
Summary generated locally
Markdown written directly to Obsidian
Requirements
macOS
Python 3
Ollama
qwen2.5:7b pulled in Ollama
PortAudio-compatible audio input
Obsidian vault folder

Python packages used:

faster-whisper
sounddevice
scipy
numpy
pyyaml
requests
Install

Clone the repo:

git clone https://github.com/YOUR_USERNAME/muesli.git
cd muesli

Create a virtual environment:

python3 -m venv .venv
source .venv/bin/activate

Install dependencies:

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

Copy the example config:

cp muesli_config.example.yaml muesli_config.yaml

Edit muesli_config.yaml and set your Obsidian meetings folder:

obsidian:
  meetings_folder: "/path/to/your/obsidian/vault/meetings"
Ollama setup

Install Ollama, then pull the meeting summary model:

ollama pull qwen2.5:7b

Check that the model is available:

ollama list
Create the terminal command

Create a small wrapper so you can run Muesli by typing muesli:

mkdir -p ~/bin

cat > ~/bin/muesli <<'WRAPPER'
#!/bin/zsh
cd "$HOME/muesli" || exit 1
exec "$HOME/muesli/.venv/bin/python" "$HOME/muesli/muesli_meeting.py"
WRAPPER

chmod +x ~/bin/muesli

Make sure ~/bin is in your path:

grep -qxF 'export PATH="$HOME/bin:$PATH"' ~/.zshrc || echo 'export PATH="$HOME/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

Then run:

muesli
Usage
muesli

Flow:

Meeting name:
Press Enter to start recording.
Press Enter to stop recording.
Transcribing...
Summarizing...
Saved to Obsidian.
Output format

Muesli writes notes using this structure:

---
type: meeting
source: muesli
date: YYYY-MM-DD
meeting: Meeting Name
audio_saved: false
status: complete
tags:
  - meeting
  - muesli
---

# YYYY-MM-DD - Meeting Name

## TLDR

## Key Points

## Decisions

## Action Items

## Open Questions

## Transcript
Current model choice

Muesli currently uses:

models:
  meeting_summary: "qwen2.5:7b"

This was chosen because it is fast, local, and good enough for meeting summaries, action items, and decision extraction.

Notes on audio

The current version records from the default microphone input.

If you are on headphones during a Zoom / Meet / Teams call, mic-only capture may not hear the other person clearly. Capturing guest/system audio requires an additional routing layer such as BlackHole or Loopback and is not implemented yet.

Roadmap

Near-term:

Add chunked recording/transcription for longer meetings
Add guest/system audio capture
Improve setup script
Add better terminal status display
Add GitHub release instructions

Later:

Speaker diarization
Calendar-aware meeting titles
Hotkey launch
Simple desktop wrapper
License

Private prototype for now. License to be decided before public release.
