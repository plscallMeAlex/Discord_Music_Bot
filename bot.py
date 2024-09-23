from discord.ext import commands
from dotenv import load_dotenv
import discord
import asyncio
import yt_dlp
import urllib.parse
import urllib.request
import os
import re

PATH_TO_FFMPEG = "C:/Software/ffmpeg/bin/ffmpeg.exe"
CURRENT_SONG = None

def search_youtube(query):
    query_string = urllib.parse.urlencode({ 'search_query': query })
    html_content = urllib.request.urlopen('http://www.youtube.com/results?' + query_string)
    search_results = re.findall(r'/watch\?v=(.{11})', html_content.read().decode())
    return 'http://www.youtube.com/watch?v=' + search_results[0]

async def get_song_name(link, ytdl):
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, lambda: ytdl.extract_info(link, download=False))
    return data['title']

def clear_user_message(ctx, message):
    asyncio.create_task(asyncio.sleep(2))
    asyncio.create_task(ctx.channel.purge(limit=2, check=lambda m: m.author == ctx.author))

def run_bot():
    load_dotenv()
    TOKEN = os.getenv('discord_token')
    intents = discord.Intents.default()
    intents.message_content = True
    client = commands.Bot(command_prefix="//", intents=intents)

    voice_clients = {}
    queues = {}
    yt_dl_options = {"format": "bestaudio/best"}
    ytdl = yt_dlp.YoutubeDL(yt_dl_options)

    ffmpeg_options = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5','options': '-vn -filter:a "volume=0.25"'}

    @client.event
    async def on_ready():
        print(f'{client.user} is now jamming')

    async def play_next(ctx):
        if queues[ctx.guild.id] != []:
            # Fetch the first song in the queue
            link = queues[ctx.guild.id].pop(0)
            await play(ctx, link)

    @client.command(name="play")
    async def play(ctx, link, *args):
        try:
            # Check if the bot is already in a voice channel
            voice_client = ctx.voice_client
            if voice_client is None:
                voice_client = await ctx.author.voice.channel.connect()
                voice_clients[ctx.guild.id] = voice_client

            if not re.match(r'https?://', link):
                link = " ".join([link, *args])
                link = search_youtube(link)

            # Fetch the song information
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(link, download=False))

            song = data['url']
            player = discord.FFmpegOpusAudio(song, **ffmpeg_options, executable=PATH_TO_FFMPEG)

            # Check if the bot is already playing a song
            if voice_client.is_playing() or voice_client.is_paused():
                # Add the song to the queue
                if ctx.guild.id not in queues:
                    queues[ctx.guild.id] = []
                queues[ctx.guild.id].append(link)
                await ctx.send(f"Added {data['title']} to queue!")
            else:
                global CURRENT_SONG
                CURRENT_SONG = data['title']

                # Start playing the song
                voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), client.loop))
                message = await ctx.send(f"Now playing: {data['title']}")
        except Exception as e:
            print(e)

        clear_user_message(ctx, ctx.message)

    @client.command(name="clear_queue")
    async def clear_queue(ctx):
        if ctx.guild.id in queues:
            queues[ctx.guild.id].clear()
            await ctx.send("Queue cleared!")
        else:
            await ctx.send("There is no queue to clear!")

    @client.command(name="pause")
    async def pause(ctx):
        try:
            voice_clients[ctx.guild.id].pause()
        except Exception as e:
            print(e)

    @client.command(name="resume")
    async def resume(ctx):
        try:
            voice_clients[ctx.guild.id].resume()
        except Exception as e:
            print(e)

    @client.command(name="stop")
    async def stop(ctx):
        try:
            global CURRENT_SONG
            CURRENT_SONG = None
            voice_clients[ctx.guild.id].stop()
            await voice_clients[ctx.guild.id].disconnect()
            del voice_clients[ctx.guild.id]
        except Exception as e:
            print(e)

    @client.command(name="queue")
    async def queue(ctx):
        description = ""
        embed = discord.Embed(title="Music Queues", color=0x00ff00)
    
        # Check if there is a current song
        if CURRENT_SONG:
            description += f"**Currently playing:**\n {CURRENT_SONG}\n"
    
        # Check if there are songs in the queue
        if ctx.guild.id in queues and queues[ctx.guild.id]:
            queue_list = []
            for index, song in enumerate(queues[ctx.guild.id]):
                try:
                    song_name = await get_song_name(song, ytdl)
                    queue_list.append(f"{index+1}. {song_name}")
                except Exception as e:
                    queue_list.append(f"{index+1}. Unknown Song")
                    print(f"Error getting song name: {e}")
            description += f"**Next Song:**\n" + "\n".join(queue_list)
        else:
            description += "No songs in queue"
    
        embed.description = description
        await ctx.send(embed=embed)

    @client.command(name="skip")
    async def skip (ctx):
        try:
            voice_clients[ctx.guild.id].stop()
            await play_next(ctx)
        except Exception as e:
            print(e)

    @client.command(name="join")
    async def join(ctx):
        try:
            await ctx.author.voice.channel.connect()
        except Exception as e:
            print(e)

    @client.command(name="hiran")
    async def hiran(ctx):
        await play(ctx, "https://www.youtube.com/watch?v=nvMTfOTd-ps")

    client.run(TOKEN)