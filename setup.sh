#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================"
echo "  Token Optimizer - Setup"
echo "============================================"
echo ""

# --- Detect Python 3.10+ ---
PYTHON=""
for candidate in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" &>/dev/null; then
        ver=$("$candidate" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
        major="${ver%%.*}"
        minor="${ver#*.}"
        if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "ERROR: Python 3.10+ is required but not found."
    echo "Install via: brew install python@3.12"
    exit 1
fi

echo "Using Python: $PYTHON ($($PYTHON --version))"
echo ""

# --- Create virtual environment ---
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    "$PYTHON" -m venv .venv
else
    echo "Virtual environment already exists."
fi

source .venv/bin/activate
echo "Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "Dependencies installed."
echo ""

# --- Check RTK ---
echo "Checking for RTK (optional)..."
if command -v rtk &>/dev/null; then
    echo "RTK found: $(rtk --version 2>/dev/null || echo 'installed')"
else
    echo "RTK not found. RTK provides 60-90% token savings on file context."
    echo "Install (optional): brew install rtk"
    echo "More info: https://github.com/rtk-ai/rtk"
fi
echo ""

# --- Provider selection ---
echo "Select your AI provider:"
echo "  [1] Claude CLI (uses your existing 'claude' login - no API key needed)"
echo "  [2] Claude API (requires Anthropic API key)"
echo "  [3] OpenAI / ChatGPT"
echo "  [4] Google Gemini"
echo "  [5] Custom (Ollama, LM Studio, Azure, etc.)"
echo ""
read -rp "Choice [1-5]: " choice

PROVIDER=""
API_KEY_VAR=""
API_KEY=""

case "$choice" in
    1)
        PROVIDER="claude-cli"
        if command -v claude &>/dev/null; then
            echo "Claude CLI found. Will use your existing authentication."
        else
            echo "WARNING: 'claude' command not found. Install Claude Code first."
            echo "  https://docs.anthropic.com/en/docs/claude-code"
        fi
        ;;
    2)
        PROVIDER="claude"
        API_KEY_VAR="ANTHROPIC_API_KEY"
        read -rp "Enter your Anthropic API key: " API_KEY
        ;;
    3)
        PROVIDER="openai"
        API_KEY_VAR="OPENAI_API_KEY"
        read -rp "Enter your OpenAI API key: " API_KEY
        ;;
    4)
        PROVIDER="gemini"
        API_KEY_VAR="GEMINI_API_KEY"
        read -rp "Enter your Google Gemini API key: " API_KEY
        ;;
    5)
        PROVIDER="custom"
        API_KEY_VAR="CUSTOM_API_KEY"
        read -rp "Enter your endpoint base URL [http://localhost:11434/v1]: " CUSTOM_URL
        CUSTOM_URL="${CUSTOM_URL:-http://localhost:11434/v1}"
        read -rp "Enter model name [llama3]: " CUSTOM_MODEL
        CUSTOM_MODEL="${CUSTOM_MODEL:-llama3}"
        read -rp "Enter API key (press Enter if none): " API_KEY
        ;;
    *)
        echo "Invalid choice. Defaulting to Claude CLI."
        PROVIDER="claude-cli"
        ;;
esac

# --- Write .env ---
echo ""
echo "Writing configuration to .env..."

cp .env.example .env

# Set provider
sed -i.bak "s/^LLM_PROVIDER=.*/LLM_PROVIDER=$PROVIDER/" .env

# Set API key
if [ -n "$API_KEY" ] && [ -n "$API_KEY_VAR" ]; then
    sed -i.bak "s|^${API_KEY_VAR}=.*|${API_KEY_VAR}=${API_KEY}|" .env
fi

# Set custom endpoint fields
if [ "$PROVIDER" = "custom" ]; then
    sed -i.bak "s|^CUSTOM_BASE_URL=.*|CUSTOM_BASE_URL=${CUSTOM_URL}|" .env
    sed -i.bak "s|^CUSTOM_MODEL=.*|CUSTOM_MODEL=${CUSTOM_MODEL}|" .env
fi

rm -f .env.bak

echo ""
echo "============================================"
echo "  Setup complete!"
echo "============================================"
echo ""
echo "  Provider: $PROVIDER"
echo "  Config:   .env"
echo ""
echo "  Start the server:"
echo "    ./run.sh"
echo ""
echo "  Then open: http://127.0.0.1:8765"
echo "============================================"
