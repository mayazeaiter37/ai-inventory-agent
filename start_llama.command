#!/bin/zsh
cd "${0:A:h}"
export AI_PROVIDER=ollama
export OLLAMA_MODEL=llama3.1:8b
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
if ! command -v ollama >/dev/null; then
  echo 'Ollama is not installed. Install it with: brew install ollama'
  exit 1
fi
if ! curl -fsS http://127.0.0.1:11434/api/tags >/dev/null; then
  ollama serve > /tmp/inventory-ollama.log 2>&1 &
  sleep 3
fi
ollama pull "$OLLAMA_MODEL" || exit 1
if [[ -x .venv312plus/bin/python ]]; then
  inventory_python=.venv312plus/bin/python
else
  inventory_python=.venv/bin/python
fi
"$inventory_python" manage.py migrate || exit 1
"$inventory_python" manage.py runserver 127.0.0.1:8001
