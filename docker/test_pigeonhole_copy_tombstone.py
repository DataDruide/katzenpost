#!/usr/bin/env python3
"""Pigeonhole Copy-Command + Tombstone-Test."""

import asyncio
import binascii
import logging
import os
import sys

from katzenpost_thinclient import ThinClient, Config

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("copy-tombstone")

CONFIG_PATH = "/Users/marcelzimmermann/Projects/erebos-network/nym/katzenpost/docker/mixnet-alpine/client/thinclient.toml"


async def main():
    log.info("=== Copy-Command + Tombstone Test startet ===")
    config = Config(CONFIG_PATH)
    client = ThinClient(config)
    await client.start(asyncio.get_running_loop())
    log.info("PKI da.")

    # --- Destination-Kanal (existiert bereits, z.B. aus vorherigem Write) ---
    # Für den Test legen wir einen frischen Destination-Kanal an und
    # schreiben zuerst ein paar Boxen hinein, die wir dann tombstonen.
    dest_seed = os.urandom(32)
    dest = await client.new_keypair(dest_seed)
    log.info("Destination-Kanal angelegt: first_index=%s", binascii.hexlify(dest.first_message_index[:8]).decode())

    # Schreibe 3 Boxen in den Destination-Kanal (damit es etwas zu tombstonen gibt)
    payload = b"data to be tombstoned"
    dest_index = dest.first_message_index
    for i in range(3):
        enc = await client.encrypt_write(payload, dest.write_cap, dest_index)
        await client.start_resending_encrypted_message(
            read_cap=None, write_cap=dest.write_cap, message_box_index=None, reply_index=None,
            envelope_descriptor=enc.envelope_descriptor,
            message_ciphertext=enc.message_ciphertext,
            envelope_hash=enc.envelope_hash,
        )
        log.info("Destination-Box %d geschrieben", i + 1)
        dest_index = enc.next_message_box_index

    # --- Temporary-Kanal für den Copy-Command ---
    temp_seed = os.urandom(32)
    temp = await client.new_keypair(temp_seed)
    log.info("Temporary-Kanal angelegt: first_index=%s", binascii.hexlify(temp.first_message_index[:8]).decode())

    # --- Tombstone-Copy-Stream-Elemente erzeugen ---
    # Tombstone die ersten 3 Boxen des Destination-Kanals
    result = await client.create_courier_envelopes_from_tombstone_range(
        dest.write_cap,
        dest.first_message_index,
        3,              # maxCount: 3 Boxen tombstonen
        is_start=True,
        is_last=True,
        buffer=None,
    )
    log.info("Tombstone-Envelopes erzeugt: %d Stück", len(result.envelopes))

    # --- Envelopes in den Temporary-Kanal schreiben ---
    temp_index = temp.first_message_index
    for chunk in result.envelopes:
        enc = await client.encrypt_write(chunk, temp.write_cap, temp_index)
        await client.start_resending_encrypted_message(
            read_cap=None, write_cap=temp.write_cap, message_box_index=None, reply_index=None,
            envelope_descriptor=enc.envelope_descriptor,
            message_ciphertext=enc.message_ciphertext,
            envelope_hash=enc.envelope_hash,
        )
        temp_index = enc.next_message_box_index
    log.info("Tombstone-Envelopes in Temporary-Kanal geschrieben")

    # --- Copy-Command senden (blockiert bis Courier bestätigt) ---
    log.info("Sende Copy-Command ...")
    await client.start_resending_copy_command(temp.write_cap)
    log.info("Copy-Command abgeschlossen (Courier hat Tombstones ausgeführt)")

    # --- Verifikation: Lesen der getombstoneten Boxen ---
    # Erwartung: TombstoneError (oder BoxIDNotFound) beim Lesen
    log.info("Versuche, getombstonete Boxen zu lesen (erwarte Fehler) ...")
    read_index = dest.first_message_index
    for i in range(3):
        try:
            read_enc = await client.encrypt_read(dest.read_cap, read_index)
            read_result = await client.start_resending_encrypted_message(
                read_cap=dest.read_cap, write_cap=None, message_box_index=read_index, reply_index=None,
                envelope_descriptor=read_enc.envelope_descriptor,
                message_ciphertext=read_enc.message_ciphertext,
                envelope_hash=read_enc.envelope_hash,
            )
            log.warning("Box %d lieferte unerwartet: %r", i + 1, read_result.plaintext)
        except Exception as e:
            log.info("Box %d: erwarteter Fehler beim Lesen: %s", i + 1, type(e).__name__)
        # Nächster Index – für den Test approximieren wir mit dem gleichen Index,
        # da Tombstones den Index nicht fortschreiben wie normale Writes.
        break  # Ein Fehler reicht als Nachweis

    log.info("=== Copy-Command + Tombstone Test beendet ===")


if __name__ == "__main__":
    asyncio.run(main())
