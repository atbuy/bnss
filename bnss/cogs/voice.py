import subprocess
from contextlib import redirect_stdout
from io import BytesIO
from typing import List, Optional

import discord
from discord import Interaction, VoiceChannel, VoiceClient
from discord.ext import commands
from yt_dlp import YoutubeDL

from bnss.bot import BNSSBot
from bnss.helpers import Song


class VoiceCog(commands.Cog):
    """Cog to handle voice channel related commands.

    The commands to be handled are:
        - join ✔️
        - leave ✔️
        - play ✔️
        - pause ✔️
        - resume ✔️
        - stop ✔️
        - skip ✔️
        - queue
        - volume ✔️
        - playing ✔️
    """

    def __init__(self, bot: BNSSBot):
        self.bot = bot
        self.song_queue: List[Song] = []

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

    @commands.command(name="queue", description="Show the current queue.")
    async def queue(self, ctx: Interaction):
        """Show the current queue."""

        # If the bot is not in a voice channel exit
        voice: VoiceClient = ctx.guild.voice_client
        if not voice:
            return await ctx.send("I am not in a voice channel.")

        if len(self.song_queue) == 0:
            return await ctx.send("No song currently queued.")

        # Create the embed
        embed = discord.Embed(
            title="Queue",
            description="\n".join(
                [
                    f"{i + 1}. **{song.name}**\n{song.link}"
                    for i, song in enumerate(self.song_queue)
                ]
            ),
            color=discord.Color.blurple(),
        )
        embed.set_thumbnail(url=self.song_queue[0].thumbnail)

        return await ctx.send(embed=embed)

    @commands.command(name="playing", description="Show the currently playing song.")
    async def now_playing(self, ctx: Interaction):
        """Show the currently playing song."""

        # If the bot is not in a voice channel exit
        voice: VoiceClient = ctx.guild.voice_client
        if not voice:
            return await ctx.send("I am not in a voice channel.")

        # If the bot is not playing a song exit
        if not voice.is_playing():
            return await ctx.send("I am not playing a song.")

        if len(self.song_queue) == 0:
            return await ctx.send("No song currently queued.")

        # Get the song that is currently playing
        song: Song = self.song_queue[0]

        # Create the embed
        embed = discord.Embed(
            title="Now Playing",
            description=f"**{song.name}**\n{song.link}",
            color=discord.Color.blurple(),
        )
        embed.set_thumbnail(url=song.thumbnail)
        embed.set_footer(text=f"Requested by {song.requester}")

        return await ctx.send(embed=embed)

    @commands.command(name="join", description="Join a voice channel.")
    async def join(self, ctx: commands.Context, channel: Optional[VoiceChannel] = None):
        """Join a voice channel."""

        # If no channel is specified,
        # join the user's channel
        if not ctx.author:
            return await ctx.send("You are not in a voice channel.")

        if not channel:
            channel = ctx.author.voice.channel

        # If the bot is already in a voice channel,
        # move it to the new channel
        voice: VoiceClient = ctx.guild.voice_client
        if voice:
            await voice.move_to(channel)

            return await ctx.send(f"Moved to {channel.mention}.")

        # Connect to the voice channel
        await channel.connect()
        return await ctx.send(f"Joined {channel.mention}.")

    @commands.command(name="leave", description="Leave a voice channel.")
    async def leave(self, ctx: commands.Context):
        """Leave a voice channel."""

        # If the bot is not in a voice channel,
        # return
        voice: VoiceClient = ctx.guild.voice_client
        if not voice:
            return await ctx.send("I am not in a voice channel.", ephemeral=True)

        # Disconnect from the voice channel
        await voice.disconnect()
        return await ctx.send("Left the voice channel.")

    @commands.command(name="volume", description="Change the volume of the player.")
    async def volume(self, ctx: commands.Context, volume: int):
        """Change the volume of the player."""

        # If the bot is not in a voice channel exit
        voice: VoiceClient = ctx.guild.voice_client
        if not voice:
            return await ctx.send("I am not in a voice channel.", ephemeral=True)

        # Change the volume of the player
        voice.source.volume = volume / 100
        return await ctx.send(f"Changed the volume to {volume}.", ephemeral=True)

    @commands.command(name="skip", description="Skip the current song.")
    async def skip(self, ctx: commands.Context):
        """Skip the current song and play net in queue."""

        # If the bot is not in a voice channel exit
        voice: VoiceClient = ctx.guild.voice_client
        if not voice:
            return await ctx.send("I am not in a voice channel.")

        # If the user is not in a voice channel exit
        if not ctx.author.voice:
            return await ctx.send("You are not in a voice channel.")

        # If the user is not in the same voice channel as the bot exit
        if ctx.author.voice.channel != voice.channel:
            return await ctx.send("You are not in the same voice channel as me.")

        # Check if there is a song currently playing
        if not voice.is_playing():
            return await ctx.send("There is no song currently playing.")

        # Skip the current song
        voice.stop()

        # Play the next song in the queue
        self.play_next_song(ctx)

    def play_next_song(self, ctx: commands.Context):
        """Play the next song in the queue."""

        def inner(error):
            if error:
                return

            voice = ctx.guild.voice_client
            if not voice:
                return

            # Remove current playing song
            self.song_queue.pop(0)
            song = self.song_queue[0]

            audio = discord.FFmpegPCMAudio(song.data, pipe=True, stderr=subprocess.PIPE)
            source = discord.PCMVolumeTransformer(audio)
            voice.play(source, after=self.play_next_song(ctx))

        return inner

    @commands.command(name="play", description="Play a song.")
    async def play(self, ctx: commands.Context, *, query: str):
        """Play a song using the spotify API library."""

        # If the user is not in a voice channel exit
        if not ctx.author.voice:
            return await ctx.send("You are not in a voice channel.")

        # Join the channel the user is in
        voice = ctx.guild.voice_client
        if not voice:
            await ctx.author.voice.channel.connect()
            voice = ctx.guild.voice_client

        # If the user is not in the same voice channel as the bot exit
        if ctx.author.voice.channel != voice.channel:
            return await ctx.send("You are not in the same voice channel as me.")

        # Only allow youtube links since the bot only uses yt-dlp
        if not query.startswith("https://www.youtube.com/watch?v="):
            # Check the length of the video and the filesize

            await ctx.send("You need to provide a valid Youtube link.")
            return

        # https://github.com/yt-dlp/yt-dlp/issues/3298#issuecomment-1181754989
        # Should be a valid way to download the song into BytesIO
        # and then convert into a discord.FFmpegPCMAudio object
        buffer = BytesIO()
        with redirect_stdout(buffer), YoutubeDL(self.ytdl_opts) as ytdlp:
            info = ytdlp.extract_info(query, download=False)

            song = Song._from_info(info)
            song.requester = ctx.author.name

            self.song_queue.append(song)

            # Check if the song is OK to be downloaded and played
            if not self.is_valid_song(info):
                return await ctx.send("Song is too long or too large.")

            await ctx.send("Downloading and playing song")

            # Download the song into the buffer
            ytdlp.download([query])

        buffer.seek(0)
        song.data = buffer

        if voice.is_playing():
            return await ctx.send("Added song to queue.")

        audio = discord.FFmpegPCMAudio(buffer, pipe=True, stderr=subprocess.PIPE)
        source = discord.PCMVolumeTransformer(audio)
        voice.play(source, after=self.play_next_song(ctx))

    @commands.command(name="pause", description="Pause the player.")
    async def pause(self, ctx: commands.Context):
        """Pause the player."""

        # If the bot is not in a voice channel exit
        voice: VoiceClient = ctx.guild.voice_client
        if not voice:
            return await ctx.send("I am not in a voice channel.", ephemeral=True)

        # Pause the player
        voice.pause()
        return await ctx.send("Paused the player.")

    @commands.command(name="resume", description="Resume the player.")
    async def resume(self, ctx: commands.Context):
        """Resume the player."""

        # If the bot is not in a voice channel exit
        voice: VoiceClient = ctx.guild.voice_client
        if not voice:
            return await ctx.send("I am not in a voice channel.", ephemeral=True)

        # Resume the player
        voice.resume()
        return await ctx.send("Resumed the player.")

    @commands.command(name="stop", description="Stop the player.")
    async def stop(self, ctx: commands.Context):
        """Stop the player."""

        # If the bot is not in a voice channel exit
        voice: VoiceClient = ctx.guild.voice_client
        if not voice:
            return await ctx.send("I am not in a voice channel.", ephemeral=True)

        # Stop the player
        voice.stop()
        return await ctx.send("Stopped the player.")
