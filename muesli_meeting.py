#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import queue
import re
import subprocess
import threading
import wave
from datetime import date, datetime
from pathlib import Path

import numpy as np
import requests
import sounddevice as sd
import yaml
from faster_whisper import WhisperModel


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

## Discussion Summary

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


def open_chunk_file(session_id, meeting_name, chunk_index, sample_rate):
    filename = f"{session_id}_{safe_filename(meeting_name)}_chunk_{chunk_index:03d}.wav"
    path = TEMP_AUDIO_DIR / filename

    wav = wave.open(str(path), "wb")
    wav.setnchannels(1)
    wav.setsampwidth(2)
    wav.setframerate(sample_rate)

    return path, wav


def disk_writer_thread(
    audio_queue,
    ready_chunks,
    stop_event,
    sample_rate,
    chunk_seconds,
    session_id,
    meeting_name,
):
    chunk_index = 1
    frames_written = 0
    frames_per_chunk = int(sample_rate * chunk_seconds)

    current_path, current_wav = open_chunk_file(
        session_id=session_id,
        meeting_name=meeting_name,
        chunk_index=chunk_index,
        sample_rate=sample_rate,
    )

    print(f"[muesli] opened temp chunk: {current_path.name}")

    while not stop_event.is_set() or not audio_queue.empty():
        try:
            frames = audio_queue.get(timeout=0.2)
        except queue.Empty:
            continue

        frames = np.nan_to_num(frames)
        frames = np.clip(frames, -1.0, 1.0)
        frames_int16 = np.int16(frames * 32767)

        current_wav.writeframes(frames_int16.tobytes())
        frames_written += len(frames_int16)

        if frames_written >= frames_per_chunk:
            current_wav.close()
            ready_chunks.append(current_path)
            print(f"[muesli] closed temp chunk: {current_path.name}")

            chunk_index += 1
            frames_written = 0

            current_path, current_wav = open_chunk_file(
                session_id=session_id,
                meeting_name=meeting_name,
                chunk_index=chunk_index,
                sample_rate=sample_rate,
            )
            print(f"[muesli] opened temp chunk: {current_path.name}")

        audio_queue.task_done()

    current_wav.close()

    if current_path.exists() and current_path.stat().st_size > 44:
        ready_chunks.append(current_path)
        print(f"[muesli] closed final temp chunk: {current_path.name}")
    elif current_path.exists():
        current_path.unlink(missing_ok=True)

    print("[muesli] disk writer stopped.")


def record_chunks_until_enter(meeting_name, config):
    TEMP_AUDIO_DIR.mkdir(exist_ok=True)

    device_index, device_info, sample_rate = get_default_input_info()
    chunk_seconds = int(config.get("audio", {}).get("chunk_seconds", 45))
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"[muesli] input device: {device_info['name']}")
    print(f"[muesli] sample rate: {sample_rate}")
    print(f"[muesli] chunk length: {chunk_seconds}s")
    print()

    audio_queue = queue.Queue(maxsize=200)
    ready_chunks = []
    stop_event = threading.Event()

    writer = threading.Thread(
        target=disk_writer_thread,
        args=(
            audio_queue,
            ready_chunks,
            stop_event,
            sample_rate,
            chunk_seconds,
            session_id,
            meeting_name,
        ),
        daemon=True,
    )

    def callback(indata, frame_count, time_info, status):
        if status:
            print(f"[muesli] audio warning: {status}")

        try:
            audio_queue.put_nowait(indata.copy())
        except queue.Full:
            print("[muesli] warning: audio queue full; dropping frames")

    input("Press Enter to start recording...")

    writer.start()

    print()
    print("[muesli] recording started.")
    print("[muesli] audio is being written to temporary chunks.")
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
    print("[muesli] finishing temp audio chunks...")

    stop_event.set()
    writer.join()

    if not ready_chunks:
        raise RuntimeError("No audio chunks were captured.")

    print(f"[muesli] chunks captured: {len(ready_chunks)}")
    print()

    return ready_chunks


def transcribe_single_chunk(model, chunk_path, language):
    segments, info = model.transcribe(
        str(chunk_path),
        beam_size=5,
        vad_filter=True,
        language=language,
    )

    transcript_parts = []

    for segment in segments:
        text = segment.text.strip()
        if text:
            transcript_parts.append(text)

    return " ".join(transcript_parts).strip(), info.language


def transcribe_chunks(chunk_paths, config):
    transcription_config = config["transcription"]
    whisper_model = transcription_config["whisper_model"]
    language = transcription_config.get("language")
    device = transcription_config["device"]
    compute_type = transcription_config["compute_type"]

    print(f"[muesli] loading transcription model: faster-whisper/{whisper_model}")
    print(f"[muesli] transcribing {len(chunk_paths)} chunk(s)...")

    model = WhisperModel(
        whisper_model,
        device=device,
        compute_type=compute_type,
    )

    transcript_parts = []
    detected_languages = []

    for index, chunk_path in enumerate(chunk_paths, start=1):
        print(f"[muesli] transcribing chunk {index}/{len(chunk_paths)}: {chunk_path.name}")

        text, detected_language = transcribe_single_chunk(
            model=model,
            chunk_path=chunk_path,
            language=language,
        )

        detected_languages.append(detected_language)

        if text:
            transcript_parts.append(text)

    transcript = "\n".join(transcript_parts).strip()
    language_summary = ", ".join(sorted(set(detected_languages)))

    print("[muesli] transcription finished.")
    print(f"[muesli] detected language(s): {language_summary}")
    print()

    return transcript


def clean_summary(summary):
    summary = summary.strip()
    summary = re.sub(r"^```markdown\s*", "", summary)
    summary = re.sub(r"^```\s*", "", summary)
    summary = re.sub(r"\s*```$", "", summary)
    return summary.strip()



def _muesli_split_text_for_summary(text, max_chars=12000):
    """
    Split long transcripts into safe chunks for local LLM summarization.
    Character-based on purpose: simple, dependency-free, and good enough for Ollama context safety.
    """
    text = (text or "").strip()
    if not text:
        return []

    paragraphs = re.split(r"\n\s*\n", text)
    chunks = []
    current = []
    current_len = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # If one paragraph is huge, split it by sentence-ish boundaries.
        if len(para) > max_chars:
            sentences = re.split(r"(?<=[.!?])\s+", para)
        else:
            sentences = [para]

        for piece in sentences:
            piece = piece.strip()
            if not piece:
                continue

            if current and current_len + len(piece) + 2 > max_chars:
                chunks.append("\n\n".join(current).strip())
                current = [piece]
                current_len = len(piece)
            else:
                current.append(piece)
                current_len += len(piece) + 2

    if current:
        chunks.append("\n\n".join(current).strip())

    return chunks


def _muesli_summary_failure(reason):
    return (
        "Summary failed.\n\n"
        f"Reason: {reason}\n\n"
        "Transcript was preserved below."
    )


def summarize_transcript(transcript, config):
    """
    Reliable summarization wrapper.

    Keeps the existing Ollama/Gemma summarizer as the core summarizer,
    but prevents long meetings from being sent as one oversized prompt.
    """
    transcript = (transcript or "").strip()

    if not transcript:
        return _muesli_summary_failure("Transcript was empty.")

    long_transcript_threshold = 16000
    chunk_size = 12000

    # Short meetings: use the original summarizer directly.
    if len(transcript) <= long_transcript_threshold:
        try:
            summary = _summarize_transcript_single(transcript, config)
            if summary and summary.strip():
                return summary.strip()
        except Exception as exc:
            return _muesli_summary_failure(exc)

        return _muesli_summary_failure("Ollama returned an empty summary.")

    # Long meetings: summarize in chunks, then synthesize.
    chunks = _muesli_split_text_for_summary(transcript, max_chars=chunk_size)

    if not chunks:
        return _muesli_summary_failure("Could not split transcript into summary chunks.")

    chunk_summaries = []

    for index, chunk in enumerate(chunks, start=1):
        chunk_prompt = (
            f"This is part {index} of {len(chunks)} from one meeting transcript.\n\n"
            "Summarize this section only. Capture decisions, action items, important context, "
            "open questions, names, dates, and project references. Be concise but specific.\n\n"
            "Transcript section:\n"
            f"{chunk}"
        )

        try:
            chunk_summary = _summarize_transcript_single(chunk_prompt, config)
            if chunk_summary and chunk_summary.strip():
                chunk_summaries.append(
                    f"Part {index}/{len(chunks)} summary:\n{chunk_summary.strip()}"
                )
            else:
                chunk_summaries.append(
                    f"Part {index}/{len(chunks)} summary failed: empty Ollama response."
                )
        except Exception as exc:
            chunk_summaries.append(
                f"Part {index}/{len(chunks)} summary failed: {exc}"
            )

    combined_summaries = "\n\n---\n\n".join(chunk_summaries).strip()

    final_prompt = (
        "Create one clean final meeting summary from these partial summaries.\n\n"
        "Use this structure:\n"
        "1. Executive summary\n"
        "2. Key decisions\n"
        "3. Action items\n"
        "4. Open questions\n"
        "5. Important context\n\n"
        "Do not mention that these were chunk summaries unless a chunk failed.\n\n"
        f"{combined_summaries}"
    )

    try:
        final_summary = _summarize_transcript_single(final_prompt, config)
        if final_summary and final_summary.strip():
            return final_summary.strip()
    except Exception as exc:
        return (
            "Partial summary created, but final synthesis failed.\n\n"
            f"Reason: {exc}\n\n"
            f"{combined_summaries}"
        )

    return (
        "Partial summary created, but final synthesis returned empty.\n\n"
        f"{combined_summaries}"
    )




def _summarize_transcript_single(transcript, config):
    model = config["models"]["meeting_summary"]
    temperature = config.get("summary", {}).get("temperature", 0.2)

    prompt = f"""You are summarizing a meeting transcript.
Note: This transcript may feature multiple speakers but lacks explicit speaker labels.

Output ONLY the following sections, using these exact Markdown headers.

Rules:
- Write the summary in the same primary language as the transcript.
- Do not translate the summary into English unless the transcript is mostly English.
- If the transcript is mixed-language, use the language used most often by the speakers.
- Preserve names, product names, and technical terms in their original form when appropriate.
- If the transcript contains any meaningful speech, TLDR must NOT be "None".
- TLDR should be useful, not overly compressed. For longer transcripts, use 3-5 bullets or 2-4 concise sentences.
- Add a Discussion Summary section after TLDR.
- Discussion Summary should explain the main arc of the conversation in 2-5 short paragraphs.
- If the conversation is educational, advisory, or exploratory rather than decision-oriented, preserve the main concepts, recommendations, and tradeoffs.
- Key Points should capture the main useful facts, even if the conversation is short or informal.
- Analyze the dialogue flow to infer distinct viewpoints and agreements.
- For Action Items and Decisions, attribute them to specific names mentioned in the text.
- If no names are mentioned, use neutral descriptive placeholders such as "One participant" or "Another participant". Do not invent roles, titles, or names.
- Put UNRESOLVED or PARKED items under Open Questions, not Decisions.
- Only list a Decision when the transcript clearly indicates a final agreement, commitment, or chosen direction.
- Do not treat opinions, suggestions, preferences, or "we need to decide" statements as Decisions; put unresolved items under Open Questions.
- If a decision was reversed during the meeting, report the FINAL decision.
- Only write "None" for Decisions, Action Items, or Open Questions if that section truly has no content.
- Do not invent details or names that are not in the transcript.

## TLDR
## Discussion Summary
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


def maybe_delete_audio_chunks(chunk_paths, config):
    should_delete = config.get("audio", {}).get("delete_temp_audio", True)

    if not should_delete:
        return

    deleted = 0
    for chunk_path in chunk_paths:
        if chunk_path.exists():
            chunk_path.unlink()
            deleted += 1

    print(f"[muesli] temporary audio chunks deleted: {deleted}")


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

    chunk_paths = record_chunks_until_enter(meeting_name, config)

    write_note(note_path, meeting_name, meeting_date, status="transcribing")
    print("[muesli] status: transcribing")

    transcript = transcribe_chunks(chunk_paths, config)

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

    maybe_delete_audio_chunks(chunk_paths, config)

    print("[muesli] meeting note updated with TLDR.")
    print("[muesli] status: complete")
    print(f"[muesli] saved to: {note_path}")
    print()


if __name__ == "__main__":
    main()
