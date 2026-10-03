#ifndef COMMAND_PARSER_H
#define COMMAND_PARSER_H

#include <Arduino.h>

// ── Configuration ─────────────────────────────────────────────────────────────
#define CMD_MAX_ARGS    10
#define CMD_BUFFER_SIZE 1000  // octets réservés une fois pour toutes

// ── Argument ──────────────────────────────────────────────────────────────────

struct Argument {
  String key;
  String value;
};

// ── CommandParser ─────────────────────────────────────────────────────────────

/**
 * Parse une commande de la forme :
 *   <commande> <arg1>=<val1>;<arg2>=<val2>;...
 *
 * Conçu pour être instancié UNE SEULE FOIS et réutilisé :
 * le buffer interne est alloué une fois dans le constructeur,
 * puis modifié en place à chaque appel de parse().
 *
 * Utilisation typique :
 *   CommandParser parser;           // une fois, en membre de classe
 *   parser.parse("configure ssid=azerty;port=5555");
 *   String ssid = parser.getArgValue("ssid");
 */
class Command {
public:
  /**
   * Constructeur : réserve CMD_BUFFER_SIZE octets pour le buffer interne.
   * À appeler une seule fois (membre de classe, variable globale, etc.)
   */
  Command();

  // ── Parsing en place ───────────────────────────────────────────────────────

  /**
   * Parse une nouvelle chaîne en réutilisant le buffer interne.
   * Les résultats précédents sont écrasés.
   *
   * @param input  Chaîne brute à parser
   */
  void parse(const String& input);

  // ── Accesseurs ─────────────────────────────────────────────────────────────

  /**
   * Retourne la valeur associée à une clé.
   *
   * @param key  Clé recherchée (sensible à la casse)
   * @return     Valeur trouvée, ou "" si absente
   */
  String getArgValue(const String& key) const;

  /** Retourne le nom de la commande. */
  const String& getCommand() const { return _command; }

  /** Retourne le nombre d'arguments parsés. */
  int getArgCount() const { return _argCount; }

private:
  String   _buffer;               // buffer principal réservé une fois
  String   _command;              // pointe dans _buffer (via substring)
  Argument _args[CMD_MAX_ARGS];   // paires clé/valeur
  int      _argCount;

  /** Remet à zéro les résultats du parsing précédent. */
  void _reset();
};

#endif // COMMAND_PARSER_H