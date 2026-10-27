import asyncio
from katzenpost_thinclient import ThinClient, Config

CONFIG_PATH = "/Users/marcelzimmermann/Projects/erebos-network/nym/katzenpost/docker/mixnet-alpine/client/thinclient.toml"

async def main():
    config = Config(CONFIG_PATH)
    client = ThinClient(config)

    await client.start(asyncio.get_running_loop())
    print(f"Thin Client gestartet. Verbunden: {client.is_connected()}")

    await asyncio.sleep(5)
    print(f"Nach 5s – Verbunden: {client.is_connected()}")

    client.stop()
    print("Thin Client gestoppt.")

asyncio.run(main())
