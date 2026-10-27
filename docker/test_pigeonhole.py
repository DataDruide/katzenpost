#!/usr/bin/env python3
"""Pigeonhole Write + Read Test mit Debug-Logging."""

import asyncio
import binascii
import logging
import os
import struct
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
    log.info("=== Pigeonhole Write+Read Test startet ===")
    config = Config(CONFIG_PATH)
    client = ThinClient(config)
    await client.start(asyncio.get_running_loop())
    log.info("PKI da.")

    # --- Keypair: write_cap, read_cap, first_index ---
    seed = os.urandom(32)
    kp = await client.new_keypair(seed)
    write_cap = kp.write_cap
    read_cap = kp.read_cap
    first_index = kp.first_message_index
    describe(write_cap, "write_cap")
    describe(read_cap, "read_cap")
    describe(first_index, "first_message_index")

    # --- Write ---
    payload = b"hello pigeonhole"
    enc = await client.encrypt_write(payload, write_cap, first_index)
    log.info("Write verschlüsselt, sende ...")
    write_result = await client.start_resending_encrypted_message(
        read_cap=None, write_cap=write_cap, message_box_index=None, reply_index=None,
        envelope_descriptor=enc.envelope_descriptor,
        message_ciphertext=enc.message_ciphertext,
        envelope_hash=enc.envelope_hash,
    )
    log.info("Write abgeschlossen: courier_queue_id=%r", write_result.courier_queue_id)

    # --- Read ---
    log.info("Lese Box zurück ...")
    read_enc = await client.encrypt_read(read_cap, first_index)
    read_result = await client.start_resending_encrypted_message(
        read_cap=read_cap, write_cap=None, message_box_index=first_index, reply_index=None,
        envelope_descriptor=read_enc.envelope_descriptor,
        message_ciphertext=read_enc.message_ciphertext,
        envelope_hash=read_enc.envelope_hash,
    )
    log.info("Read-Ergebnis: plaintext=%r", read_result.plaintext)

    if read_result.plaintext == payload:
        log.info("✓ ROUNDTRIP ERFOLGREICH: Gelesene Daten stimmen mit geschriebenen überein.")
    else:
        log.error("✗ MISMATCH: geschrieben=%r gelesen=%r", payload, read_result.plaintext)


if __name__ == "__main__":
    asyncio.run(main())
