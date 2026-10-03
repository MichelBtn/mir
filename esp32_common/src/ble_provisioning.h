#ifndef BLE_PROVISIONING_H
#define BLE_PROVISIONING_H

#include <Arduino.h>
#include <functional>

// ── BleProvisioning ─────────────────────────────────────────────────────────
//
// Gestion du provisioning WiFi via BLE :
// - actif pendant une fenêtre de 60 s après le boot (défaut),
//   en parallèle de la connexion WiFi STA en cours ;
// - si une demande de configuration est reçue pendant cette fenêtre
//   (connexion BLE ou écriture SSID/PWD), on bascule en mode configuration
//   qui reste actif aussi longtemps que nécessaire ;
// - récupère uniquement le SSID et le mot de passe, transmis via le
//   callback onCredentials() pour stockage (ex. préférences ap1_ssid/ap1_pwd).
//
// Protocole BLE : un service + 3 caractéristiques
// - WRITE ssid   : SSID du point d'accès (tronqué à 32 car.)
// - WRITE pwd    : mot de passe (vide accepté = réseau ouvert, tronqué à 64 car.)
// - READ/NOTIFY status : WAIT_CREDENTIALS, RECEIVED_SSID, RECEIVED_PWD, ...
//
// Utilisation typique (voir main.cpp) :
//   BleProvisioning bleProv;
//   bleProv.onCredentials([](const String& ssid, const String& pwd) {
//     // sauvegarder en préférences, notifier, stopper, rebooter
//   });
//   bleProv.begin("MIR_esp_0");   // avant connect_to_ap(), pour le parallèle
//   bleProv.handle();             // dans loop()
class BleProvisioning {
 public:
  using CredentialsCallback = std::function<void(const String& ssid, const String& pwd)>;

  static const uint32_t DEFAULT_TIMEOUT_MS = 60 * 1000;

  explicit BleProvisioning(uint32_t timeout_ms = DEFAULT_TIMEOUT_MS);

  // Enregistre le callback appelé dès que SSID + écriture PWD reçus.
  // L'ordre d'écriture SSID/PWD est quelconque.
  // Note : le callback est invoqué depuis handle() (contexte loop()), jamais
  // depuis les callbacks BLE : il peut donc stopper le BLE et rebooter.
  void onCredentials(CredentialsCallback cb) { _credentialsCb = cb; }

  // Démarre l'advertising BLE. À appeler avant (ou pendant) la connexion
  // WiFi pour fonctionner en parallèle. Sans effet si déjà actif.
  void begin(const String& deviceName);

  // À appeler dans loop() : coupe le BLE après le timeout, sauf si une
  // demande de configuration a été reçue (mode persistant).
  void handle();

  // Arrête l'advertising et libère la stack BLE. Sans effet si inactif.
  void stop();

  // Envoie un message de statut via la caractéristique NOTIFY (si active).
  void notifyStatus(const char* msg);

  bool isActive() const { return _active; }
  bool isConfigRequested() const { return _configRequested; }

  // Événements internes appelés depuis les callbacks BLE (contexte tâche BT).
  void handleConnect();
  void handleDisconnect();
  void handleWrite(bool isSsid, const String& value);

 private:
  void tryComplete();

  static const char* SERVICE_UUID;
  static const char* SSID_CHAR_UUID;
  static const char* PWD_CHAR_UUID;
  static const char* STATUS_CHAR_UUID;

  uint32_t _timeoutMs;
  volatile bool _active = false;
  volatile bool _configRequested = false;  // demande reçue pendant la fenêtre
  volatile bool _credentialsPending = false;  // paire SSID/PWD complète, à traiter dans handle()
  bool _pwdWritten = false;                // écriture PWD reçue (même vide)
  unsigned long _startMs = 0;
  String _ssid = "";
  String _pwd = "";
  CredentialsCallback _credentialsCb;

  class ServerCallbacks;
  class WriteCallbacks;
  friend class ServerCallbacks;
  friend class WriteCallbacks;

  // Pointeurs non propriétaires (alloués par la stack BLE) : uniquement
  // valides tant que _active. Remis à nullptr dans stop().
  void* _server = nullptr;
  void* _statusChar = nullptr;
};

#endif  // BLE_PROVISIONING_H
