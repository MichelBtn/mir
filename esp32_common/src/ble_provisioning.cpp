#include "ble_provisioning.h"

#include <BLE2902.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <WiFi.h>

const char* BleProvisioning::SERVICE_UUID = "e0f0c9a0-4d1a-4e8b-9f2c-abcdef123401";
const char* BleProvisioning::SSID_CHAR_UUID = "e0f0c9a0-4d1a-4e8b-9f2c-abcdef123402";
const char* BleProvisioning::PWD_CHAR_UUID = "e0f0c9a0-4d1a-4e8b-9f2c-abcdef123403";
const char* BleProvisioning::STATUS_CHAR_UUID = "e0f0c9a0-4d1a-4e8b-9f2c-abcdef123404";

static const size_t BLE_PROV_SSID_MAX_LEN = 32;
static const size_t BLE_PROV_PWD_MAX_LEN = 64;
static const size_t BLE_PROV_NAME_MAX_LEN = 28;

// Callbacks BLE : simples relais vers l'instance (contexte tâche BT).
class BleProvisioning::ServerCallbacks : public BLEServerCallbacks {
 public:
  explicit ServerCallbacks(BleProvisioning* prov) : _prov(prov) {}
  void onConnect(BLEServer* server) override {
    if (_prov) _prov->handleConnect();
  }
  void onDisconnect(BLEServer* server) override {
    if (_prov) _prov->handleDisconnect();
  }

 private:
  BleProvisioning* _prov;
};

class BleProvisioning::WriteCallbacks : public BLECharacteristicCallbacks {
 public:
  WriteCallbacks(BleProvisioning* prov, bool isSsid) : _prov(prov), _isSsid(isSsid) {}
  void onWrite(BLECharacteristic* characteristic) override {
    if (!_prov) return;
    _prov->handleWrite(_isSsid, String(characteristic->getValue().c_str()));
  }

 private:
  BleProvisioning* _prov;
  bool _isSsid;
};

BleProvisioning::BleProvisioning(uint32_t timeout_ms) : _timeoutMs(timeout_ms) {}

void BleProvisioning::begin(const String& deviceName) {
  if (_active) {
    return;
  }
  _ssid = "";
  _pwd = "";
  _pwdWritten = false;
  _configRequested = false;
  _credentialsPending = false;

  String bleName = deviceName.substring(0, BLE_PROV_NAME_MAX_LEN);

  // Coexistence WiFi + BLE : le modem sleep est obligatoire tant que le
  // Bluetooth est activé (sinon abort du driver WiFi au WiFi.begin()).
  WiFi.setSleep(WIFI_PS_MIN_MODEM);
  BLEDevice::init(bleName.c_str());
  BLEServer* server = BLEDevice::createServer();
  server->setCallbacks(new ServerCallbacks(this));

  BLEService* service = server->createService(SERVICE_UUID);

  BLECharacteristic* ssidChar =
      service->createCharacteristic(SSID_CHAR_UUID, BLECharacteristic::PROPERTY_WRITE);
  ssidChar->setCallbacks(new WriteCallbacks(this, true));

  BLECharacteristic* pwdChar =
      service->createCharacteristic(PWD_CHAR_UUID, BLECharacteristic::PROPERTY_WRITE);
  pwdChar->setCallbacks(new WriteCallbacks(this, false));

  BLECharacteristic* statusChar = service->createCharacteristic(
      STATUS_CHAR_UUID, BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_NOTIFY);
  statusChar->addDescriptor(new BLE2902());
  statusChar->setValue("WAIT_CREDENTIALS");

  _server = server;
  _statusChar = statusChar;

  service->start();

  BLEAdvertising* advertising = BLEDevice::getAdvertising();
  advertising->addServiceUUID(SERVICE_UUID);
  advertising->setScanResponse(true);
  BLEDevice::startAdvertising();

  _active = true;
  _startMs = millis();

  Serial.print("BLE provisioning actif (");
  Serial.print(bleName);
  Serial.println(") pendant 60 s après le boot.");
}

void BleProvisioning::handle() {
  if (!_active) {
    return;
  }
  // Paire complète reçue : on exécute le callback ici (contexte loop()) et
  // non dans le callback GATT (contexte tâche BT), pour que la réponse ATT
  // d'écriture soit envoyée au client avant stop()/reboot. Sans cela, le
  // client reçoit une erreur GATT alors que la sauvegarde a réussi.
  if (_credentialsPending) {
    _credentialsPending = false;
    _pwdWritten = false;  // exige une paire fraîche pour un prochain cycle
    if (_credentialsCb) {
      _credentialsCb(_ssid, _pwd);
    }
    return;
  }
  if (_configRequested) {
    return;  // mode configuration : reste actif aussi longtemps que nécessaire
  }
  if (millis() - _startMs >= _timeoutMs) {
    Serial.println("BLE provisioning : aucune demande reçue pendant 60 s, arrêt.");
    stop();
  }
}

void BleProvisioning::stop() {
  if (!_active) {
    return;
  }
  _active = false;
  _statusChar = nullptr;
  _server = nullptr;
  BLEDevice::stopAdvertising();
  BLEDevice::deinit(true);
  // BLE coupé : on peut repasser en pleine performance WiFi.
  WiFi.setSleep(WIFI_PS_NONE);
  Serial.println("BLE provisioning arrêté.");
}

void BleProvisioning::notifyStatus(const char* msg) {
  Serial.print("BLE provisioning : ");
  Serial.println(msg);
  auto* statusChar = static_cast<BLECharacteristic*>(_statusChar);
  if (statusChar != nullptr) {
    statusChar->setValue(msg);
    statusChar->notify();
  }
}


void BleProvisioning::handleConnect() {
  // Toute connexion pendant la fenêtre = demande de configuration.
  if (_active) {
    _configRequested = true;
  }
  notifyStatus(_ssid.isEmpty() ? "WAIT_CREDENTIALS" : "RECEIVED_SSID");
}

void BleProvisioning::handleDisconnect() {
  if (_active) {
    // On relance l'advertising : en mode configuration on reste joignable
    // sans limite de durée, sinon l'arrêt après timeout est géré par handle().
    BLEDevice::startAdvertising();
  }
}

void BleProvisioning::handleWrite(bool isSsid, const String& rawValue) {
  if (!_active) {
    return;
  }
  // Première écriture reçue : on passe en mode configuration persistant.
  _configRequested = true;
  String value = rawValue;
  value.trim();
  if (isSsid) {
    _ssid = value.substring(0, BLE_PROV_SSID_MAX_LEN);
    Serial.print("BLE provisioning : SSID reçu (");
    Serial.print(_ssid.length());
    Serial.println(" car.).");
    notifyStatus("RECEIVED_SSID");
  } else {
    _pwd = value.substring(0, BLE_PROV_PWD_MAX_LEN);
    _pwdWritten = true;
    Serial.print("BLE provisioning : mot de passe reçu (");
    Serial.print(_pwd.length()); 
    Serial.println(" car.).");
    notifyStatus("RECEIVED_PWD");
  }
  tryComplete();
}

void BleProvisioning::tryComplete() {
  // SSID obligatoire, mot de passe optionnel (réseau ouvert accepté) : le
  // client doit écrire la caractéristique PWD au moins une fois (même vide).
  // On ne fait que lever un drapeau : le callback est exécuté dans handle().
  if (_ssid.isEmpty() || !_pwdWritten) {
    return;
  }
  _credentialsPending = true;
}
