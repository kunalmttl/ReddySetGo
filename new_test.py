# test_login.py
from telethon import TelegramClient

import config

client = TelegramClient(config.SESSION_NAME, config.API_ID, config.API_HASH)


async def main():
    await client.start()
    me = await client.get_me()
    print(me.id, me.username, me.phone)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
