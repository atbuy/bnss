import logging
import queue
import subprocess
from collections import defaultdict, namedtuple
from contextlib import redirect_stdout
from io import BytesIO
from typing import Optional

import discord
from discord import VoiceChannel, VoiceClient
from discord.ext import commands, tasks
from yt_dlp import YoutubeDL

from bnss.bot import BNSSBot
from bnss.helpers import Song, VoiceSettings
from bnss.logger import log


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
        - loop ✔️
        - queue ✔️
        - volume ✔️
        - playing ✔️
    """

    def __init__(self, bot: BNSSBot):
        self.bot = bot
        self.default_settings = VoiceSettings()
        self.guild_voice = defaultdict(lambda: VoiceSettings)
        self.__lock = False
        self.__next_download = queue.Queue()

        self.DownloadArgs = namedtuple("DownloadArgs", ("ctx", "voice", "query"))

        self.ytdl_opts = {
            "format": "bestaudio/best",
            "outtmpl": "-",
            "logtostderr": True,
            "quiet": True,
            "no_warnings": True,
        }

        self.disconnect_task.start()
        self.download_task.start()

    @tasks.loop(seconds=1)
    async def download_task(self):
        """Get the next query from the download queue and download it."""

        if self.__next_download.empty():
            return

        song = self.__next_download.get()
        loop = self.bot.loop

        self.__lock = True
        await loop.run_in_executor(
            None,
            self.queue_song,
            song.ctx,
            song.voice,
            song.query,
        )
        self.__lock = False

        log("Downloaded song.", song.query)

    @download_task.before_loop
    async def before_download_task(self):
        """Wait for the bot to be ready."""

        await self.bot.wait_until_ready()

    @tasks.loop(minutes=2)
    async def disconnect_task(self):
        """Check if the bot should be disconnected."""

        voices = self.bot.voice_clients
        if not voices:
            return

        for voice in voices:
            if not voice.is_playing():
                await voice.disconnect()

    @disconnect_task.before_loop
    async def before_disconnect_task(self):
        """Wait for the bot to be ready."""

        await self.bot.wait_until_ready()

    def is_valid_song(self, info: dict) -> bool:
        """Check if the filesize and duration of a song is OK,"""

        # Check if the song is too long
        if info["duration"] > 600:
            return False

        # Check if the song is too large
        if info["filesize"] > 20_000_000:
            return False

        return True

    def queue_song(self, ctx: commands.Context, voice: VoiceClient, query: str):
        """Download a song and queue it."""

        settings = self.guild_voice[ctx.guild]

        # https://github.com/yt-dlp/yt-dlp/issues/3298#issuecomment-1181754989
        # Should be a valid way to download the song into BytesIO
        # and then convert into a discord.FFmpegPCMAudio object
        buffer = BytesIO()
        with redirect_stdout(buffer), YoutubeDL(self.ytdl_opts) as ytdlp:
            info = ytdlp.extract_info(query, download=False)

            song = Song._from_info(info)
            song.requester = ctx.author.name

            # Check if the song is OK to download and play
            if not self.is_valid_song(info):
                log("Not a valid song.", level=logging.ERROR)
                self._result = "The song is too large or too long to download."
                return

            # Download the song into the buffer
            try:
                ytdlp.download([query])
            except Exception as e:
                log(str(e), level=logging.ERROR)
                self._result = "Can't download song. Please try another URL."
                return

        buffer.seek(0)
        song.data = buffer
        settings.queue.put(song)

        if voice.is_playing():
            log("Song added to queue.", level=logging.INFO)
            self._result = "Song added to queue."
            return

        audio = discord.FFmpegPCMAudio(buffer, pipe=True, stderr=subprocess.PIPE)
        source = discord.PCMVolumeTransformer(audio)
        source.volume = settings.volume / 100
        voice.play(source, after=self.play_next_song(ctx))

        self._result = "Playing song."

    @commands.command(name="loop", description="Loop current song.")
    async def loop(self, ctx: commands.Context):
        """Loop current playing son indefinitely."""

        settings = self.guild_voice[ctx.guild]
        settings.loop = not settings.loop

        action = "L" if settings.loop else "Stopped l"
        await ctx.send(f"{action}ooping song.")

    @commands.command(name="queue", description="Show the song queue.")
    async def queue(self, ctx: commands.Context):
        """Show the current queue."""

        settings = self.guild_voice[ctx.guild]

        # If the bot is not in a voice channel exit
        voice: VoiceClient = ctx.guild.voice_client
        if not voice:
            return await ctx.send("I am not in a voice channel.")

        if settings.queue.empty():
            return await ctx.send("No song currently queued.")

        # Create the embed
        songs = settings.queue.queue
        embed = discord.Embed(
            title="Queue",
            description="\n".join(
                [
                    f"{i + 1}. **{song.name}**\n{song.link}"
                    for i, song in enumerate(songs)
                ]
            ),
            color=discord.Color.blurple(),
        )
        embed.set_thumbnail(url=settings.queue.queue[0].thumbnail)

        return await ctx.send(embed=embed)

    @commands.command(name="playing", description="Show the currently playing song.")
    async def now_playing(self, ctx: commands.Context):
        """Show the currently playing song."""

        settings = self.guild_voice[ctx.guild]

        # If the bot is not in a voice channel exit
        voice: VoiceClient = ctx.guild.voice_client
        if not voice:
            return await ctx.send("I am not in a voice channel.")

        # If the bot is not playing a song exit
        if not voice.is_playing():
            return await ctx.send("I am not playing a song.")

        if settings.queue.empty():
            return await ctx.send("No song currently queued.")

        # Get the song that is currently playing
        song: Song = settings.queue.queue[0]

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
            return await ctx.send("I am not in a voice channel.")

        # Disconnect from the voice channel
        await voice.disconnect()
        return await ctx.send("Left the voice channel.")

    @commands.command(name="volume", description="Change the volume of the player.")
    async def volume(self, ctx: commands.Context, volume: int):
        """Change the volume of the player."""

        settings = self.guild_voice[ctx.guild]

        # If the bot is not in a voice channel exit
        voice: VoiceClient = ctx.guild.voice_client
        if not voice:
            return await ctx.send("I am not in a voice channel.")

        # Change the volume of the player
        settings.volume = volume
        voice.source.volume = settings.volume / 100
        return await ctx.send(f"Changed the volume to {volume}%")

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

        settings = self.guild_voice[ctx.guild]

        def inner(error):
            if error:
                return

            voice = ctx.guild.voice_client
            if not voice:
                return

            # If loop is set to True,
            # then we need to just replay the current song.
            if settings.loop:
                song = settings.queue.queue[0]
                song.data.seek(0)
            else:
                # Remove current playing song
                # and play the next one in the queue
                if settings.queue.empty():
                    return

                settings.queue.get()

                if settings.queue.empty():
                    return

                song = settings.queue.queue[0]

            # Start playing next song
            audio = discord.FFmpegPCMAudio(song.data, pipe=True, stderr=subprocess.PIPE)
            source = discord.PCMVolumeTransformer(audio)
            source.volume = settings.volume / 100
            voice.play(source, after=self.play_next_song(ctx))

        return inner

    @commands.command(name="play", description="Play a song.")
    async def play(self, ctx: commands.Context, *, query: str):
        """Play a song using the spotify API library."""

        settings = self.guild_voice[ctx.guild]

        if settings.queue.full():
            return await ctx.send("The queue is full.")

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
            await ctx.send("You need to provide a valid Youtube link.")
            return

        if self.__lock:
            await ctx.send("Your download will start shortly.")
            args = self.DownloadArgs(ctx, voice, query)
            self.__next_download.put(args)
            return

        self.__lock = True

        await ctx.send("Downloading...")
        async with ctx.typing():
            loop = self.bot.loop
            await loop.run_in_executor(None, self.queue_song, ctx, voice, query)
            await ctx.send(self._result)

        self.__lock = False

    @commands.command(name="pause", description="Pause the player.")
    async def pause(self, ctx: commands.Context):
        """Pause the player."""

        # If the bot is not in a voice channel exit
        voice: VoiceClient = ctx.guild.voice_client
        if not voice:
            return await ctx.send("I am not in a voice channel.")

        # Pause the player
        voice.pause()
        return await ctx.send("Paused the player.")

    @commands.command(name="resume", description="Resume the player.")
    async def resume(self, ctx: commands.Context):
        """Resume the player."""

        # If the bot is not in a voice channel exit
        voice: VoiceClient = ctx.guild.voice_client
        if not voice:
            return await ctx.send("I am not in a voice channel.")

        # Resume the player
        voice.resume()
        return await ctx.send("Resumed the player.")

    @commands.command(name="stop", description="Stop the player.")
    async def stop(self, ctx: commands.Context):
        """Stop the player."""

        settings = self.guild_voice[ctx.guild]

        # If the bot is not in a voice channel exit
        voice: VoiceClient = ctx.guild.voice_client
        if not voice:
            return await ctx.send("I am not in a voice channel.")

        # Stop the player, clear the queue
        # and reset the loop flag
        voice.stop()
        settings.queue.queue.clear()
        settings.loop = False

        await ctx.send("Stopped the player and cleared queue.")
