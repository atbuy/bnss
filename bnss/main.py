import asyncio
from typing import Literal

import discord
from discord.ext import commands

from bnss.bot import BNSSBot
from bnss.cogs import EventsCog, VoiceCog
from bnss.logger import setup_logger

bot = BNSSBot()


@bot.command()
@commands.guild_only()
@commands.is_owner()
async def sync(
    ctx: commands.Context,
    guilds: commands.Greedy[discord.Object],
    spec: Literal["~", "*", "^"] | None = None,
) -> None:
    """Sync all the slash commands of the bot.

    Syncs all slash commands for the bot,
    in the guild or globally.
    """

    # If no guilds are specified,
    # sync all the slash commands.
    if not guilds:
        if spec == "~":
            synced = await ctx.bot.tree.sync(guild=ctx.guild)
        elif spec == "*":
            ctx.bot.tree.copy_global_to(guild=ctx.guild)
            synced = await ctx.bot.tree.sync(guild=ctx.guild)
        elif spec == "^":
            ctx.bot.tree.clear_commands(guild=ctx.guild)
            await ctx.bot.tree.sync(guild=ctx.guild)
            synced = []
        else:
            synced = await ctx.bot.tree.sync()

        # Deide the scope of the sync
        scope = "to the current guild."
        if spec is None:
            scope = "globally."

        await ctx.send(f"Synced {len(synced)} commands {scope}")
        return

    # Sync all commands for each guild, if guilds are specified
    ret = 0
    for guild in guilds:
        try:
            await ctx.bot.tree.sync(guild=guild)
        except discord.HTTPException:
            pass
        else:
            ret += 1

    await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")


async def main(bot: BNSSBot):
    """Initialize the bot."""

    # Setup logger for bot and discord
    setup_logger(bot.settings.log_level)

    # Load cogs
    await bot.add_cog(EventsCog(bot))
    await bot.add_cog(VoiceCog(bot))

    # Run bot
    await bot.start(bot.settings.token)


if __name__ == "__main__":
    asyncio.run(main(bot))
