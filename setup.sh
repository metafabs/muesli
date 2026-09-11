#!/bin/zsh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

say() {
  printf '\n[muesli setup] %s\n' "$1"
}

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Muesli's setup script currently supports macOS only."
  exit 1
fi

say "Checking your Mac..."

if ! command -v brew >/dev/null 2>&1; then
  cat <<'MSG'

Homebrew is required to install a couple of local dependencies.

Install Homebrew by pasting this command into Terminal:

/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

When Homebrew finishes, run ./setup.sh again.
MSG
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  say "Installing Python..."
  brew install python
fi

if ! brew list portaudio >/dev/null 2>&1; then
  say "Installing PortAudio..."
  brew install portaudio
fi

if ! command -v ollama >/dev/null 2>&1; then
  say "Installing Ollama..."
  curl -fsSL https://ollama.com/install.sh | sh
fi

if ! curl -fsS http://localhost:11434/api/tags >/dev/null 2>&1; then
  say "Starting Ollama..."
  nohup ollama serve > /tmp/muesli-ollama.log 2>&1 &

  for _ in {1..30}; do
    if curl -fsS http://localhost:11434/api/tags >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
fi

if ! curl -fsS http://localhost:11434/api/tags >/dev/null 2>&1; then
  cat <<'MSG'

Ollama is installed but its local service is not responding yet.
Try running `ollama serve` in another Terminal window, then run ./setup.sh again.
MSG
  exit 1
fi

say "Creating the Python environment..."
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if [[ -f muesli_config.yaml ]]; then
  say "Existing muesli_config.yaml found; leaving it unchanged."
else
  DEFAULT_NOTES_DIR="$HOME/Documents/Muesli Meetings"
  printf '\nWhere should Muesli save meeting notes?\n'
  printf 'Press Enter for: %s\n' "$DEFAULT_NOTES_DIR"
  printf 'If you use Obsidian, you can paste a folder inside your vault instead.\n\n'
  read "NOTES_DIR?Folder: "
  NOTES_DIR="${NOTES_DIR:-$DEFAULT_NOTES_DIR}"

  NOTES_DIR="$NOTES_DIR" .venv/bin/python - <<'PY'
from pathlib import Path
import os
import yaml

notes_dir = Path(os.path.expanduser(os.environ["NOTES_DIR"])).resolve()
notes_dir.mkdir(parents=True, exist_ok=True)

config = {
    "models": {"meeting_summary": "gemma4:12b"},
    "transcription": {
        "whisper_model": "base",
        "language": None,
        "device": "cpu",
        "compute_type": "int8",
    },
    "obsidian": {"meetings_folder": str(notes_dir)},
    "audio": {"chunk_seconds": 45, "delete_temp_audio": True},
    "summary": {"temperature": 0.2},
}

Path("muesli_config.yaml").write_text(
    yaml.safe_dump(config, sort_keys=False, allow_unicode=True),
    encoding="utf-8",
)
print(f"[muesli setup] Notes will be saved to: {notes_dir}")
PY
fi

MODEL="$(.venv/bin/python - <<'PY'
import yaml
with open("muesli_config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f) or {}
print(config.get("models", {}).get("meeting_summary", "gemma4:12b"))
PY
)"

if ! ollama list | awk 'NR > 1 {print $1}' | grep -Fx "$MODEL" >/dev/null 2>&1; then
  say "Downloading the local summary model: $MODEL"
  echo "This can take a while the first time."
  ollama pull "$MODEL"
else
  say "Ollama model ready: $MODEL"
fi

say "Creating the muesli Terminal command..."
mkdir -p "$HOME/bin"
cat > "$HOME/bin/muesli" <<WRAPPER
#!/bin/zsh
cd "$SCRIPT_DIR" || exit 1
exec "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/muesli_meeting.py" "\$@"
WRAPPER
chmod +x "$HOME/bin/muesli"

PATH_LINE='export PATH="$HOME/bin:$PATH"'
if [[ ! -f "$HOME/.zshrc" ]] || ! grep -qxF "$PATH_LINE" "$HOME/.zshrc"; then
  printf '\n%s\n' "$PATH_LINE" >> "$HOME/.zshrc"
fi

cat <<'DONE'

[muesli setup] Setup complete.

Open a new Terminal window, then run:

  muesli

Muesli will ask for a meeting name. Press Enter to start recording and Enter again to stop.
DONE
