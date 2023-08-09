import discord
from discord import Activity, ActivityType
from discord.ext import commands

from bnss.settings import get_settings


class BNSSBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        self.settings = get_settings()
        self._prefix = self.settings.prefix
        self._activity = Activity(
            type=ActivityType.listening,
            name=f"{self._prefix}help",
        )
        self._intents = discord.Intents.all()
        super().__init__(
            *args,
            command_prefix=self._prefix,
            intents=self._intents,
            activity=self._activity,
            **kwargs,
        )
