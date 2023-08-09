import asyncio

from bnss.bot import BNSSBot
from bnss.logger import setup_logger


async def main():
    """Initialize the bot."""

    bot = BNSSBot()

    # Setup logger for bot and discord
    setup_logger(bot.settings.log_level)

    # Run bot
    await bot.start(bot.settings.bnss_token)


if __name__ == "__main__":
    asyncio.run(main())
