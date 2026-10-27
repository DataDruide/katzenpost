import asyncio
from katzenpost_thinclient import ThinClient, Config

CONFIG_PATH = "/Users/marcelzimmermann/Projects/erebos-network/nym/katzenpost/docker/mixnet-alpine/client/thinclient.toml"

async def main():
    pki_received = asyncio.Event()

    async def on_pki(event):
        print("PKI-Dokument empfangen.")
        pki_received.set()

    config = Config(CONFIG_PATH, on_new_pki_document=on_pki)
    client = ThinClient(config)

    await client.start(asyncio.get_running_loop())
    print(f"Thin Client gestartet. Verbunden: {client.is_connected()}")

    print("Warte auf PKI-Dokument...")
    try:
        await asyncio.wait_for(pki_received.wait(), timeout=60.0)
    except asyncio.TimeoutError:
        print("Timeout: Kein PKI-Dokument innerhalb von 60s.")
        client.stop()
        return

    print("Suche echo-Dienst...")
    desc = client.get_service("echo")
    dest_node, dest_queue = desc.to_destination()
    print(f"Echo gefunden: node_hash={dest_node.hex()[:16]}..., queue={dest_queue.hex()[:16]}...")

    print("Sende Nachricht an echo...")
    reply = await client.blocking_send_message(
        b"Hello Mixnet from Erebos",
        dest_node,
        dest_queue,
        timeout_seconds=60.0,
    )
    print(f"Reply empfangen: {reply!r}")

    client.stop()
    print("Fertig.")

asyncio.run(main())
