import os
import asyncio
import discord
from discord.ext import commands
import yt_dlp
from flask import Flask
import threading

# 1. Flask Web Sunucusu (UptimeRobot ve Render için)
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot aktif ve çalışıyor!"

# 2. Bot Ayarları
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# yt_dlp ve FFmpeg ayarları (cookies.txt ve güncellenmiş format eklendi)
ytdl_format_options = {
    'format': 'bestaudio/best/best',
    'noplaylist': True,
    'quiet': True,
    'cookiefile': 'cookies.txt',  # YouTube engellemesini aşmak için çerez dosyası
    'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        
        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

@bot.event
async def on_ready():
    print(f'{bot.user} olarak giriş yapıldı!')

@bot.command(name='play', help='YouTube\'dan müzik çalar.')
async def play(ctx, *, search: str):
    print(f"Play komutu alındı: {search}")
    
    if not ctx.author.voice:
        await ctx.send("Önce bir ses kanalına girmelisin!")
        return

    channel = ctx.author.voice.channel
    
    try:
        if ctx.voice_client is None:
            await channel.connect()
        elif ctx.voice_client.channel != channel:
            await ctx.voice_client.move_to(channel)
    except Exception as e:
        print(f"Ses kanalına bağlanırken hata: {e}")
        await ctx.send(f"Ses kanalına bağlanamadım! Hata: {e}")
        return

    async with ctx.typing():
        if not search.startswith("http"):
            search = f"ytsearch:{search}"
            
        try:
            player = await YTDLSource.from_url(search, loop=bot.loop, stream=True)
        except Exception as e:
            print(f"YouTube veri çekme hatası (yt-dlp): {e}")
            await ctx.send(f"Şarkı bilgisi alınamadı! Hata: {e}")
            return
            
        try:
            ctx.voice_client.play(player, after=lambda e: print(f'Oynatma bitti / Hata: {e}') if e else print("Oynatma sorunsuz bitti."))
        except Exception as e:
            print(f"Play metodunda hata: {e}")
            await ctx.send(f"Müzik başlatılamadı! Hata: {e}")
            return

    await ctx.send(f'Şu an çalınıyor: **{player.title}**')

@bot.command(name='dur', help='Müziği durdurur ve bottan çıkar.')
async def stop(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("Ses kanalından ayrıldım.")

# 3. Başlatma Bloğu (Flask dan Botu Birlikte Çalıştırır)
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    # Flask sunucusunu arka planda thread ile başlatıyoruz ki botla çakışmasın
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=port)).start()
    
    # Discord botunu başlatıyoruz
    bot.run(os.environ.get('DISCORD_BOT_TOKEN'))