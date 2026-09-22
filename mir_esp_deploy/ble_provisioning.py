"""Provisioning BLE des capteurs MIR (bleak, API synchrone).

Protocole (cf. src/ble_provisioning.cpp) :
- Nom BLE : MIR_<sensor_id>, service e0f0c9a0-...-01
- WRITE ssid (...02), WRITE pwd (...03, vide accepté = réseau ouvert)
- READ/NOTIFY status (...04) : WAIT_CREDENTIALS, RECEIVED_SSID, RECEIVED_PWD, SUCCESS:rebooting

Se connecter dans les 60 s après le boot = demande de configuration
(le device reste alors joignable sans limite de durée).

Exemple :
    prov = BleProvisioner()
    prov.connect()              # lève RuntimeError si introuvable
    prov.set_ap("MonAP", "pwd") # True si SUCCESS:rebooting reçu
    prov.disconnect()
"""

import asyncio
import threading

from bleak import BleakClient, BleakScanner

SERVICE = "e0f0c9a0-4d1a-4e8b-9f2c-abcdef123401"
SSID_CHAR = "e0f0c9a0-4d1a-4e8b-9f2c-abcdef123402"
PWD_CHAR = "e0f0c9a0-4d1a-4e8b-9f2c-abcdef123403"
STATUS_CHAR = "e0f0c9a0-4d1a-4e8b-9f2c-abcdef123404"


class BleProvisioner:
    """Enveloppe synchrone autour de bleak (boucle asyncio en thread dédié)."""

    def __init__(self):
        self._name_prefix = "MIR_ESP_SENSOR"
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._client = None
        self._device = None
        self.last_status = None
        self._success = threading.Event()

    # ── plumbing sync/async ──────────────────────────────────────────────
    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _call(self, coro, timeout=30.0):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout)

    def _on_status(self, _, data):
        status = bytes(data).decode(errors="replace")
        self.last_status = status
        if status == "SUCCESS:rebooting":
            self._success.set()

    # ── API synchrone ────────────────────────────────────────────────────
    def connect(self, timeout=20.0):
        """Scanne et se connecte. Retourne l'adresse. Lève RuntimeError sinon."""
        return self._call(self._connect(timeout), timeout=timeout + 10)

    def set_ap(self, ssid, pwd="", success_timeout=10.0):
        """Écrit SSID puis PWD. Retourne True si SUCCESS:rebooting reçu.

        PWD vide accepté (réseau ouvert). Après succès le device reboote :
        la déconnexion qui suit est normale.
        """
        self._success.clear()
        self._call(self._write(ssid, pwd))
        return self._success.wait(success_timeout)

    def disconnect(self):
        """Déconnecte et arrête la boucle. À appeler en fin d'utilisation."""
        try:
            if self._client is not None:
                self._call(self._client.disconnect(), timeout=10.0)
        finally:
            self._client = None
            self._loop.call_soon_threadsafe(self._loop.stop)

    # ── coroutines internes ──────────────────────────────────────────────
    async def _connect(self, timeout):
        def match(d, ad):
            try:
                uuids = [u.lower() for u in ad.service_uuids]
            except (AttributeError, TypeError):
                uuids = []
            return (d.name or "").startswith(self._name_prefix) or SERVICE.lower() in uuids

        dev = await BleakScanner.find_device_by_filter(match, timeout=timeout)
        if dev is None:
            raise RuntimeError("équipement non trouvé (hors fenêtre 60 s après boot ?)")
        self._device = dev
        self._client = BleakClient(dev)
        await self._client.connect()
        self.last_status = (await self._client.read_gatt_char(STATUS_CHAR)).decode()
        await self._client.start_notify(STATUS_CHAR, self._on_status)
        return dev.address

    async def _write(self, ssid, pwd):
        if self._client is None:
            raise RuntimeError("non connecté : appeler connect() d'abord")
        if isinstance(pwd, str):
            pwd = pwd.encode()
        await self._client.write_gatt_char(SSID_CHAR, ssid.encode(), response=True)
        await self._client.write_gatt_char(PWD_CHAR, pwd, response=True)

    # ── context manager ──────────────────────────────────────────────────
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.disconnect()
        return False


if __name__ == "__main__":
    with BleProvisioner() as prov:
        print("connecté :", prov.connect())
        print("status initial :", prov.last_status)
        ok = prov.set_ap("toto", "tutu")
        print("provisioning :", "OK (reboot en cours)" if ok else "ÉCHEC (pas de SUCCESS:rebooting)")
