#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import subprocess
from datetime import date, datetime
from pathlib import Path

import numpy as np
import requests
import sounddevice as sd
import yaml
from faster_whisper import WhisperModel
from scipy.io.wavfile import write as write_wav


CONFIG_PATH = Path(__file__).with_name("muesli_config.yaml")
TEMP_AUDIO_DIR = Path(__file__).with_name("temp_audio")

RESET = "\033[0m"
BOLD = "\033[1m"

GREEN = "\033[38;5;115m"
MINT = "\033[38;5;121m"
BLUE = "\033[38;5;117m"
YELLOW = "\033[38;5;222m"
PINK = "\033[38;5;218m"
LAVENDER = "\033[38;5;183m"
GRAY = "\033[38;5;245m"


def color(text, code):
    return f"{code}{text}{RESET}"


def print_header():
    print()
    print(
        "      "
        + color("✦", MINT)
        + "  "
        + color("·", YELLOW)
        + "  "
        + color("✧", PINK)
        + "        "
        + color("✦", BLUE)
        + "  "
        + color("·", LAVENDER)
        + "  "
        + color("✧", GREEN)
    )
    print("   " + color("╭────────────────────────────╮", GRAY))
    print(
        "   "
        + color("│", GRAY)
        + "        "
        + color("m u e s l i", MINT + BOLD)
        + "          "
        + color("│", GRAY)
    )
    print("   " + color("╰────────────────────────────╯", GRAY))
    print(
        "      "
        + color("✧", BLUE)
        + "  "
        + color("·", PINK)
        + "  "
        + color("✦", YELLOW)
        + "        "
        + color("✧", GREEN)
        + "  "
        + color("·", MINT)
        + "  "
        + color("✦", LAVENDER)
    )
    print()
    print(color("local-first ai meeting notes → obsidian", GRAY))
    print(color("v0.1.0  ·  by Fabien Hameline", GRAY))
    print()


def load_config():
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Missing config file: {CONFIG_PATH}")

    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def check_obsidian_folder(config):
    folder = Path(config["obsidian"]["meetings_folder"])

    if not folder.exists():
        raise FileNotFoundError(f"Obsidian meetings folder not found: {folder}")

    print(f"[muesli] output folder ready: {folder}")


def check_ollama_model(config):
    model = config["models"]["meeting_summary"]

    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            check=True,
        )
    except Exception as e:
        raise RuntimeError("Could not run `ollama list`. Is Ollama installed?") from e

    if model not in result.stdout:
        raise RuntimeError(f"Configured model not found in Ollama: {model}")

    print(f"[muesli] model ready: {model}")


def clean_meeting_name(raw_name):
    name = raw_name.strip()
    if not name:
        return "Untitled Meeting"
    return name


def safe_filename(text):
    cleaned = "".join(c for c in text if c.isalnum() or c in (" ", "-", "_")).strip()
    return cleaned.replace(" ", "_") or "Untitled_Meeting"


def markdown_safe_title(text):
    return text.replace("\n", " ").strip()


def get_note_path(config, meeting_name, meeting_date):
    folder = Path(config["obsidian"]["meetings_folder"])
    filename = f"{meeting_date} - {safe_filename(meeting_name).replace('_', ' ')}.md"
    return folder / filename


def build_note_content(meeting_name, meeting_date, status, summary_body=None, transcript=None):
    title = f"{meeting_date} - {markdown_safe_title(meeting_name)}"

    if summary_body is None:
        summary_body = """## TLDR

## Key Points

## Decisions

## Action Items

## Open Questions"""

    if transcript is None:
        transcript = ""

    return f"""---
type: meeting
source: muesli
date: {meeting_date}
meeting: {meeting_name}
audio_saved: false
status: {status}
tags:
  - meeting
  - muesli
---

# {title}

{summary_body.strip()}

## Transcript

{transcript.strip()}
"""


def write_note(note_path, meeting_name, meeting_date, status, summary_body=None, transcript=None):
    content = build_note_content(
        meeting_name=meeting_name,
        meeting_date=meeting_date,
        status=status,
        summary_body=summary_body,
        transcript=transcript,
    )
    note_path.write_text(content, encoding="utf-8")


def get_default_input_info():
    device_index = sd.default.device[0]
    device_info = sd.query_devices(device_index, "input")
    sample_rate = int(device_info["default_samplerate"])
    return device_index, device_info, sample_rate


def record_until_enter(meeting_name):
    TEMP_AUDIO_DIR.mkdir(exist_ok=True)

    device_index, device_info, sample_rate = get_default_input_info()

    print(f"[muesli] input device: {device_info['name']}")
    print(f"[muesli] sample rate: {sample_rate}")
    print()

    frames = []

    def callback(indata, frame_count, time_info, status):
        if status:
            print(f"[muesli] audio warning: {status}")
        frames.append(indata.copy())

    input("Press Enter to start recording...")

    print()
    print("[muesli] recording started.")
    print("[muesli] press Enter to stop.")
    print()

    with sd.InputStream(
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
        callback=callback,
        device=device_index,
    ):
        input("Press Enter to stop recording...")

    print()
    print("[muesli] recording stopped.")

    if not frames:
        raise RuntimeError("No audio frames captured.")

    audio = np.concatenate(frames, axis=0)
    audio = np.nan_to_num(audio)
    audio = np.clip(audio, -1.0, 1.0)
    audio_int16 = np.int16(audio * 32767)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{safe_filename(meeting_name)}.wav"
    audio_path = TEMP_AUDIO_DIR / filename

    write_wav(audio_path, sample_rate, audio_int16)

    duration_seconds = len(audio_int16) / sample_rate
    print(f"[muesli] audio saved temporarily: {audio_path}")
    print(f"[muesli] duration: {duration_seconds:.1f}s")
    print()

    return audio_path


def transcribe_audio(audio_path, config):
    transcription_config = config["transcription"]
    whisper_model = transcription_config["whisper_model"]
    language = transcription_config.get("language")
    device = transcription_config["device"]
    compute_type = transcription_config["compute_type"]

    print(f"[muesli] loading transcription model: faster-whisper/{whisper_model}")
    print("[muesli] transcribing...")

    model = WhisperModel(
        whisper_model,
        device=device,
        compute_type=compute_type,
    )

    segments, info = model.transcribe(
        str(audio_path),
        beam_size=5,
        vad_filter=True,
        language=language,
    )

    transcript_parts = []

    for segment in segments:
        text = segment.text.strip()
        if text:
            transcript_parts.append(text)

    transcript = " ".join(transcript_parts).strip()

    print("[muesli] transcription finished.")
    print(f"[muesli] detected language: {info.language}")
    print()

    return transcript


def clean_summary(summary):
    summary = summary.strip()
    summary = re.sub(r"^```markdown\s*", "", summary)
    summary = re.sub(r"^```\s*", "", summary)
    summary = re.sub(r"\s*```$", "", summary)
    return summary.strip()


def summarize_transcript(transcript, config):
    model = config["models"]["meeting_summary"]
    temperature = config.get("summary", {}).get("temperature", 0.2)

    prompt = f"""You are summarizing a meeting transcript.

Output ONLY the following sections, using these exact Markdown headers.

Rules:
- If the transcript contains any meaningful speech, TLDR must NOT be "None".
- TLDR should be 1-2 concise sentences explaining what the conversation was about.
- Key Points should capture the main useful facts, even if the conversation is short or informal.
- Capture every action item with its owner and any due date.
- Put UNRESOLVED or PARKED items under Open Questions, not Decisions.
- If a decision was reversed during the meeting, report the FINAL decision.
- Only write "None" for Decisions, Action Items, or Open Questions if that section truly has no content.
- Do not invent details that are not in the transcript.

## TLDR
## Key Points
## Decisions
## Action Items
## Open Questions

Transcript:
{transcript}
"""

    print(f"[muesli] summarizing with {model}...")

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        },
        timeout=180,
    )

    response.raise_for_status()
    data = response.json()

    summary = clean_summary(data.get("response", ""))

    if not summary:
        raise RuntimeError("Ollama returned an empty summary.")

    print("[muesli] summary finished.")
    print()

    return summary


def maybe_delete_audio(audio_path, config):
    should_delete = config.get("audio", {}).get("delete_temp_audio", True)

    if should_delete and audio_path.exists():
        audio_path.unlink()
        print("[muesli] temporary audio deleted.")


def main():
    print_header()
    print("[muesli] checking local stack...")

    config = load_config()
    check_obsidian_folder(config)
    check_ollama_model(config)

    print("[muesli] ready.")
    print()

    meeting_name = clean_meeting_name(input("Meeting name: "))
    meeting_date = date.today().isoformat()
    note_path = get_note_path(config, meeting_name, meeting_date)

    print()
    print(f"[muesli] meeting: {meeting_name}")
    print(f"[muesli] date: {meeting_date}")
    print(f"[muesli] note: {note_path}")
    print()

    write_note(note_path, meeting_name, meeting_date, status="recording")
    print("[muesli] meeting note created in Obsidian.")
    print("[muesli] status: recording")
    print()

    audio_path = record_until_enter(meeting_name)

    write_note(note_path, meeting_name, meeting_date, status="transcribing")
    print("[muesli] status: transcribing")

    transcript = transcribe_audio(audio_path, config)

    write_note(
        note_path,
        meeting_name,
        meeting_date,
        status="transcribed",
        transcript=transcript,
    )
    print("[muesli] transcript written to Obsidian.")
    print("[muesli] status: transcribed")
    print()

    write_note(
        note_path,
        meeting_name,
        meeting_date,
        status="summarizing",
        transcript=transcript,
    )
    print("[muesli] status: summarizing")

    summary = summarize_transcript(transcript, config)

    write_note(
        note_path,
        meeting_name,
        meeting_date,
        status="complete",
        summary_body=summary,
        transcript=transcript,
    )

    maybe_delete_audio(audio_path, config)

    print("[muesli] meeting note updated with TLDR.")
    print("[muesli] status: complete")
    print(f"[muesli] saved to: {note_path}")
    print()


if __name__ == "__main__":
    main()
