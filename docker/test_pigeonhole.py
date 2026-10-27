#!/usr/bin/env python3
"""Pigeonhole-Write-Test mit Debug-Logging – basierend auf der echten API."""

import asyncio
import binascii
import logging
import os
import sys
import traceback

from katzenpost_thinclient import ThinClient, Config

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("pigeonhole-test")

CONFIG_PATH = "/Users/marcelzimmermann/Projects/erebos-network/nym/katzenpost/docker/mixnet-alpine/client/thinclient.toml"


def describe(obj, name):
    if isinstance(obj, (bytes, bytearray)):
        log.debug("%s: type=bytes len=%d hex_prefix=%s",
                  name, len(obj), binascii.hexlify(obj[:64]).decode())
    else:
        log.debug("%s: type=%s repr=%s", name, type(obj).__name__, repr(obj)[:160])


async def main():
    log.info("=== Pigeonhole-Test startet ===")
    config = Config(CONFIG_PATH)
    client = ThinClient(config)
    await client.start(asyncio.get_running_loop())
    log.info("PKI da.")

    geom = getattr(client, "pigeonhole_geometry", None)
    log.info("Pigeonhole Geometry: %s", geom)

    # 1. Keypair erzeugen
    seed = os.urandom(32)
    describe(seed, "seed")
    kp = await client.new_keypair(seed)
    write_cap = kp.write_cap
    first_index = kp.first_message_index
    describe(write_cap, "write_cap")
    describe(first_index, "first_message_index")

    # 2. Write verschlüsseln
    payload = b"hello pigeonhole"
    describe(payload, "payload")
    enc = await client.encrypt_write(payload, write_cap, first_index)
    describe(enc.envelope_descriptor, "envelope_descriptor")
    describe(enc.message_ciphertext, "message_ciphertext")
    describe(enc.envelope_hash, "envelope_hash")
    describe(enc.next_message_box_index, "next_message_box_index")

    # 3. Senden
    log.info("Rufe start_resending_encrypted_message auf ...")
    try:
        result = await client.start_resending_encrypted_message(
            read_cap=None,
            write_cap=write_cap,
            message_box_index=None,
            reply_index=None,
            envelope_descriptor=enc.envelope_descriptor,
            message_ciphertext=enc.message_ciphertext,
            envelope_hash=enc.envelope_hash,
        )
        log.info("Write abgeschlossen: %r", result)
    except Exception as e:
        log.error("Write fehlgeschlagen: %s", e)
        log.error("Traceback:\n%s", traceback.format_exc())
        raise

    log.info("=== Pigeonhole-Test beendet ===")


if __name__ == "__main__":
    asyncio.run(main())
