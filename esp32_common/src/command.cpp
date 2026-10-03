#include "command.h"



// ── Constructeur ──────────────────────────────────────────────────────────────
Command::Command() : _argCount(0) {
  _buffer.reserve(CMD_BUFFER_SIZE);   // allocation unique sur le heap
  _command.reserve(32);               // petite réserve pour la commande
}

// ── _reset ────────────────────────────────────────────────────────────────────

void Command::_reset() {
  _command = "";        // remet à zéro sans désallouer (capacité conservée)
  _argCount = 0;
  for (int i = 0; i < CMD_MAX_ARGS; i++) {
    _args[i].key   = "";
    _args[i].value = "";
  }
}

// ── parse ─────────────────────────────────────────────────────────────────────

void Command::parse(const String& input) {
  _reset();

  // Copie dans le buffer interne (déjà alloué, pas de réallocation si
  // input.length() <= CMD_BUFFER_SIZE)
  _buffer = input;
  _buffer.trim();

  // 1. Isoler la commande (tout ce qui précède le premier espace)
  int spaceIndex = _buffer.indexOf(' ');
  if (spaceIndex == -1) {
    _command = _buffer;
    return;
  }

  _command = _buffer.substring(0, spaceIndex);

  // 2. Travailler directement dans _buffer à partir de la partie arguments
  int startPos = spaceIndex + 1;

  // Trim gauche de la partie arguments
  while (startPos < (int)_buffer.length() && _buffer[startPos] == ' ') {
    startPos++;
  }

  // 3. Découper les paires par ';'
  while (startPos < (int)_buffer.length() && _argCount < CMD_MAX_ARGS) {
    int semicolonIndex = _buffer.indexOf(';', startPos);

    int pairEnd;
    if (semicolonIndex == -1) {
      pairEnd  = _buffer.length();        // dernier segment
    } else {
      pairEnd  = semicolonIndex;
    }

    // Trim droit du segment
    int trimEnd = pairEnd;
    while (trimEnd > startPos && _buffer[trimEnd - 1] == ' ') trimEnd--;

    // 4. Chercher '=' dans le segment [startPos, trimEnd)
    int eqIndex = -1;
    for (int i = startPos; i < trimEnd; i++) {
      if (_buffer[i] == '=') { eqIndex = i; break; }
    }

    if (eqIndex != -1) {
      Argument& arg = _args[_argCount];

      // substring() crée de nouvelles String, mais dans des buffers déjà
      // dimensionnés grâce à la réserve initiale de _buffer
      arg.key   = _buffer.substring(startPos, eqIndex);
      arg.value = _buffer.substring(eqIndex + 1, trimEnd);
      arg.key.trim();
      arg.value.trim();
      _argCount++;
    }

    startPos = (semicolonIndex == -1) ? _buffer.length() : semicolonIndex + 1;
  }
}

// ── getArgValue ───────────────────────────────────────────────────────────────

String Command::getArgValue(const String& key) const {
  for (int i = 0; i < _argCount; i++) {
    if (_args[i].key == key) {
      return _args[i].value;
    }
  }
  return "";
}