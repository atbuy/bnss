import subprocess
from contextlib import redirect_stdout
from io import BytesIO
from typing import Optional

import discord
from discord import Interaction, VoiceChannel, VoiceClient
from discord import app_commands as slash
from discord.ext import commands
from yt_dlp import YoutubeDL

from bnss.bot import BNSSBot


class VoiceCog(commands.Cog):
    """Cog to handle voice channel related commands.

    The commands to be handled are:
        - join ✔️
        - leave ✔️
        - play ✔️
        - pause ✔️
        - resume ✔️
        - stop ✔️
        - skip
        - queue
        - volume ✔️
        - now_playing
    """

    def __init__(self, bot: BNSSBot):
        self.bot = bot
        self.song_queue = []

        self.ytdl_opts = {
            "format": "bestaudio/best",
            "outtmpl": "-",
            "logtostderr": True,
            "quiet": True,
            "no_warnings": True,
        }

    def is_valid_song(self, info: dict) -> bool:
        """Check if the filesize and duration of a song is OK,"""

        # Check if the song is too long
        if info["duration"] > 600:
            return False

        # Check if the song is too large
        if info["filesize"] > 20_000_000:
            return False

        return True

    @slash.command(name="join", description="Join a voice channel.")
    async def join(self, ctx: Interaction, channel: Optional[VoiceChannel] = None):
        """Join a voice channel."""

        reply = ctx.response.send_message

        # If no channel is specified,
        # join the user's channel
        if not ctx.user.voice:
            return await reply("You are not in a voice channel.", ephemeral=True)

        if not channel:
            channel = ctx.user.voice.channel

        # If the bot is already in a voice channel,
        # move it to the new channel
        voice: VoiceClient = ctx.guild.voice_client
        if voice:
            await voice.move_to(channel)

            return await reply(f"Moved to {channel.mention}.")

        # Connect to the voice channel
        await channel.connect()
        return await reply(f"Joined {channel.mention}.")

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
        return await reply("Left the voice channel.")

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

    @slash.command(name="play", description="Play a song.")
    async def play(self, ctx: Interaction, *, query: str):
        """Play a song using the spotify API library."""

        reply = ctx.response.send_message

        # If the bot is not in a voice channel exit
        voice: VoiceClient = ctx.guild.voice_client
        if not voice:
            return await reply("I am not in a voice channel.", ephemeral=True)

        # If the user is not in a voice channel exit
        if not ctx.user.voice:
            return await reply("You are not in a voice channel.", ephemeral=True)

        # If the user is not in the same voice channel as the bot exit
        if ctx.user.voice.channel != voice.channel:
            return await reply(
                "You are not in the same voice channel as me.", ephemeral=True
            )

        # Check if there is a song currently playing
        if voice.is_playing():
            # Add the song to the queue
            # TODO Load songs from a queue
            self.song_queue.append(query)
            return await reply("Already playing another song.")

        # Only allow youtube links since the bot only uses yt-dlp
        if not query.startswith("https://www.youtube.com/watch?v="):
            # Check the length of the video and the filesize

            await reply("You need to provide a valid Youtube link.", ephemeral=True)
            return

        # https://github.com/yt-dlp/yt-dlp/issues/3298#issuecomment-1181754989
        # Should be a valid way to download the song into BytesIO
        # and then convert into a discord.FFmpegPCMAudio object
        buffer = BytesIO()
        with redirect_stdout(buffer), YoutubeDL(self.ytdl_opts) as ytdlp:
            info = ytdlp.extract_info(query, download=False)

            # Check if the song is OK to be downloaded and played
            if not self.is_valid_song(info):
                return await reply("Song is too long or too large.", ephemeral=True)

            await reply("Downloading and playing song.", ephemeral=True)

            # Download the song into the buffer
            ytdlp.download([query])

        buffer.seek(0)

        audio = discord.FFmpegPCMAudio(buffer, pipe=True, stderr=subprocess.PIPE)
        source = discord.PCMVolumeTransformer(audio)
        voice.play(source)

    @slash.command(name="pause", description="Pause the player.")
    async def pause(self, ctx: Interaction):
        """Pause the player."""

        reply = ctx.response.send_message

        # If the bot is not in a voice channel exit
        voice: VoiceClient = ctx.guild.voice_client
        if not voice:
            return await reply("I am not in a voice channel.", ephemeral=True)

        # Pause the player
        voice.pause()
        return await reply("Paused the player.")

    @slash.command(name="resume", description="Resume the player.")
    async def resume(self, ctx: Interaction):
        """Resume the player."""

        reply = ctx.response.send_message

        # If the bot is not in a voice channel exit
        voice: VoiceClient = ctx.guild.voice_client
        if not voice:
            return await reply("I am not in a voice channel.", ephemeral=True)

        # Resume the player
        voice.resume()
        return await reply("Resumed the player.")

    @slash.command(name="stop", description="Stop the player.")
    async def stop(self, ctx: Interaction):
        """Stop the player."""

        reply = ctx.response.send_message

        # If the bot is not in a voice channel exit
        voice: VoiceClient = ctx.guild.voice_client
        if not voice:
            return await reply("I am not in a voice channel.", ephemeral=True)

        # Stop the player
        voice.stop()
        return await reply("Stopped the player.")
