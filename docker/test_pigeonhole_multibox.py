#!/usr/bin/env python3
"""Pigeonhole Multi-Box Write+Read Test mit Längenprefix."""

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
log = logging.getLogger("pigeonhole-multibox")

CONFIG_PATH = "/Users/marcelzimmermann/Projects/erebos-network/nym/katzenpost/docker/mixnet-alpine/client/thinclient.toml"

# Nutzlast pro Box laut Geometrie (aus deinem Log: 1549)
MAX_BOX_PAYLOAD = 1549


def describe(obj, name):
    if isinstance(obj, (bytes, bytearray)):
        log.debug("%s: type=bytes len=%d hex_prefix=%s",
                  name, len(obj), binascii.hexlify(obj[:64]).decode())
    else:
        log.debug("%s: type=%s repr=%s", name, type(obj).__name__, repr(obj)[:160])


async def main():
    log.info("=== Pigeonhole Multi-Box Test startet ===")
    config = Config(CONFIG_PATH)
    client = ThinClient(config)
    await client.start(asyncio.get_running_loop())
    log.info("PKI da.")

    geom = getattr(client, "pigeonhole_geometry", None)
    log.info("Pigeonhole Geometry: %s", geom)
    if geom:
        max_payload = getattr(geom, "max_plaintext_payload_length", MAX_BOX_PAYLOAD)
    else:
        max_payload = MAX_BOX_PAYLOAD
    log.info("Max plaintext payload per box: %d", max_payload)

    # --- Keypair ---
    seed = os.urandom(32)
    kp = await client.new_keypair(seed)
    write_cap = kp.write_cap
    read_cap = kp.read_cap
    current_write_index = kp.first_message_index
    current_read_index = kp.first_message_index
    describe(write_cap, "write_cap")
    describe(read_cap, "read_cap")

    # --- Payload erzeugen: 4-Byte-BE-Längenprefix + Daten ---
    # Datenmenge so wählen, dass sie auf mehrere Boxen passt (z.B. 4000 Bytes)
    original_payload = b"MULTIBOX:" + os.urandom(4000)
    length_prefix = struct.pack(">I", len(original_payload))
    full_payload = length_prefix + original_payload
    log.info("Original payload len=%d, mit Prefix len=%d", len(original_payload), len(full_payload))
    describe(full_payload[:32], "full_payload_head")

    # --- Write: Payload in Chunks aufteilen ---
    chunk_size = max_payload
    chunks = [full_payload[i:i+chunk_size] for i in range(0, len(full_payload), chunk_size)]
    log.info("Schreibe %d Boxen (chunk_size=%d) ...", len(chunks), chunk_size)

    write_index = current_write_index
    for i, chunk in enumerate(chunks):
        enc = await client.encrypt_write(chunk, write_cap, write_index)
        result = await client.start_resending_encrypted_message(
            read_cap=None, write_cap=write_cap, message_box_index=None, reply_index=None,
            envelope_descriptor=enc.envelope_descriptor,
            message_ciphertext=enc.message_ciphertext,
            envelope_hash=enc.envelope_hash,
        )
        log.info("Box %d/%d geschrieben (len=%d)", i+1, len(chunks), len(chunk))
        write_index = enc.next_message_box_index

    # --- Read: Boxen nacheinander lesen, bis Länge erreicht ---
    log.info("Lese Boxen zurück ...")
    accumulated = b""
    total_expected = None
    box_count = 0

    read_index = current_read_index
    while True:
        read_enc = await client.encrypt_read(read_cap, read_index)
        read_result = await client.start_resending_encrypted_message(
            read_cap=read_cap, write_cap=None, message_box_index=read_index, reply_index=None,
            envelope_descriptor=read_enc.envelope_descriptor,
            message_ciphertext=read_enc.message_ciphertext,
            envelope_hash=read_enc.envelope_hash,
        )
        box_count += 1
        chunk = read_result.plaintext
        if chunk is None:
            log.warning("Box %d lieferte None", box_count)
            break
        describe(chunk, f"box_{box_count}_plaintext")
        accumulated += chunk
        log.info("Box %d gelesen (len=%d, accumulated=%d)", box_count, len(chunk), len(accumulated))

        # Beim ersten Chunk: Längenprefix extrahieren
        if total_expected is None and len(accumulated) >= 4:
            total_expected = struct.unpack(">I", accumulated[:4])[0]
            log.info("Längenprefix gelesen: total_expected=%d", total_expected)

        if total_expected is not None and len(accumulated) >= 4 + total_expected:
            break

        # Nächster Index
        read_index = read_enc.next_message_box_index

        # Sicherheitsgrenze
        if box_count > 20:
            log.error("Zu viele Boxen gelesen, breche ab.")
            break

    # --- Vergleich ---
    if total_expected is None:
        log.error("Kein Längenprefix gelesen.")
        return

    recovered = accumulated[4:4+total_expected]
    if recovered == original_payload:
        log.info("✓ MULTI-BOX ROUNDTRIP ERFOLGREICH: %d Bytes aus %d Boxen korrekt rekonstruiert.",
                 len(recovered), box_count)
    else:
        log.error("✗ MISMATCH: original=%d recovered=%d", len(original_payload), len(recovered))
        log.error("Original head: %s", binascii.hexlify(original_payload[:32]).decode())
        log.error("Recovered head: %s", binascii.hexlify(recovered[:32]).decode())


if __name__ == "__main__":
    asyncio.run(main())
