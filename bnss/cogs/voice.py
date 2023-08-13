from typing import Optional

from discord import Interaction, VoiceChannel, VoiceClient
from discord import app_commands as slash
from discord.ext import commands


class VoiceCog(commands.Cog):
    """Cog to handle voice channel related commands.

    The commands to be handled are:
        - join ✔️
        - leave ✔️
        - play
        - pause
        - resume
        - stop
        - skip
        - queue
        - volume ✔️
        - now_playing
    """

    @slash.command(name="join", description="Join a voice channel.")
    async def join(self, ctx: Interaction, channel: Optional[VoiceChannel] = None):
        """Join a voice channel."""

        reply = ctx.response.send_message

        # If no channel is specified,
        # join the user's channel
        if not channel:
            channel = ctx.user.voice.channel

        # If the bot is already in a voice channel,
        # move it to the new channel
        voice: VoiceClient = ctx.guild.voice_client
        if voice:
            await voice.move_to(channel)

            return await reply(f"Moved to {channel.mention}.", ephemeral=True)

        # Connect to the voice channel
        await channel.connect()
        return await reply(f"Joined {channel.mention}.", ephemeral=True)

    @slash.command(name="leave", description="Leave a voice channel.")
    async def leave(self, ctx: Interaction):
        """Leave a voice channel."""

        reply = ctx.response.send_message

        # If the bot is not in a voice channel,
        # return
        voice: VoiceClient = ctx.guild.voice_client
        if not voice:
            return await reply("I am not in a voice channel.", ephemeral=True)

        # Disconnect from the voice channel
        await voice.disconnect()
        return await reply("Left the voice channel.", ephemeral=True)

    @slash.command(name="volume", description="Change the volume of the player.")
    async def volume(self, ctx: Interaction, volume: int):
        """Change the volume of the player."""

        reply = ctx.response.send_message

        # If the bot is not in a voice channel exit
        voice: VoiceClient = ctx.guild.voice_client
        if not voice:
            return await reply("I am not in a voice channel.", ephemeral=True)

        # Change the volume of the player
        voice.source.volume = volume / 100
        return await reply(f"Changed the volume to {volume}.", ephemeral=True)
