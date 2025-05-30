import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
from discord import app_commands
import asyncio
import json

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
print(f"Token: {TOKEN}")

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

def load_bad_words():
    try:
        with open('bad_words.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            return [word.lower() for word in data.get('slurs', [])]
    except FileNotFoundError:
        print("bad_words.json file not found!")
        return []
    except Exception as e:
        print(f"Error loading bad words: {e}")
        return []

def contains_bad_word(message_content, bad_words):
    message_lower = message_content.lower()
    for bad_word in bad_words:
        if bad_word in message_lower:
            return True
    return False

class Bot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='/', intents=intents)
        
    async def setup_hook(self):
        print("Loading extensions...")
        for folder in ['general', 'admin', 'utils', 'roblox']:
            await self.load_extension(f'commands.{folder}.{folder}')
        
        print("Syncing slash commands...")
        try:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} command(s)")
        except Exception as e:
            print(f"Failed to sync commands: {e}")

bot = Bot()

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    print(f'Bot is ready in {len(bot.guilds)} guild(s)')

    await bot.tree.sync()
    print("Forcefully synced commands")
    
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="Waffle Crunch"))

def get_join_leave_channel(guild):
    try:
        if not os.path.exists('configs.json'):
            return None
            
        with open('configs.json', 'r') as f:
            configs = json.load(f)
            
        if 'joinleave' not in configs or 'guilds' not in configs['joinleave']:
            return None
            
        guild_id = str(guild.id)
        if guild_id in configs['joinleave']['guilds']:
            channel_id = configs['joinleave']['guilds'][guild_id]['channel_id']
            return guild.get_channel(channel_id)
            
        if 'channel' in configs['joinleave']:
            default_channel = configs['joinleave']['channel']
            return discord.utils.get(guild.text_channels, name=default_channel)
            
        return None
    except Exception as e:
        print(f"Error getting join/leave channel: {e}")
        return None

@bot.event
async def on_member_join(member):
    embed = discord.Embed(
        title="New Member! 🎉",
        description=f"Welcome {member.mention}! Thank you for joining our server!",
        color=discord.Color.green()
    )
    embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
    embed.add_field(name="Join Date", value=member.joined_at.strftime("%d/%m/%Y, %H:%M:%S"), inline=True)
    embed.set_footer(text=f"Member Count: {member.guild.member_count}")
    
    channel = get_join_leave_channel(member.guild)
    
    if not channel:
        channel = discord.utils.get(member.guild.text_channels, name="joins")
        if not channel:
            channel = next((channel for channel in member.guild.text_channels if channel.permissions_for(member.guild.me).send_messages), None)
    
    if channel:
        await channel.send(embed=embed)

@bot.event
async def on_member_remove(member):
    embed = discord.Embed(
        title="Member Left.",
        description=f"{member.mention} left the server...",
        color=discord.Color.red()
    )
    embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
    embed.add_field(name="Leave Date", value=discord.utils.utcnow().strftime("%d/%m/%Y, %H:%M:%S"), inline=True)
    embed.set_footer(text=f"Member Count: {member.guild.member_count}")
    
    channel = get_join_leave_channel(member.guild)
    
    if not channel:
        channel = discord.utils.get(member.guild.text_channels, name="joins")
        if not channel:
            channel = next((channel for channel in member.guild.text_channels if channel.permissions_for(member.guild.me).send_messages), None)
    
    if channel:
        await channel.send(embed=embed)

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    # Kötü kelime kontrolü
    bad_words = load_bad_words()
    if contains_bad_word(message.content, bad_words):
        await message.delete()
        embed = discord.Embed(
            title="⚠️ You have been warned",
            description=f"{message.author.mention} Please don't use that word here.",
            color=discord.Color.red()
        )
        await message.channel.send(embed=embed, delete_after=10)
        return
    
    # Mevcut kontroller
    if "wfl sucks" in message.content.lower() or "waffle sucks" in message.content.lower():
        await message.delete()
        await message.channel.send(f"{message.author.mention} You suck 😡")
        return
    elif "this bot sucks" in message.content.lower():
        await message.delete()
        await message.channel.send(f"{message.author.mention} You suck 😡")
        return
    elif "this bot is good" in message.content.lower():
        await message.delete()
        await message.channel.send(f"{message.author.mention} Thank you 😊")
        return

    await bot.process_commands(message)

bot.run(TOKEN, log_handler=handler, log_level=logging.DEBUG)