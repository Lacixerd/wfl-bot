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
        # Check if config file exists
        if not os.path.exists('configs.json'):
            return None
            
        # Load config
        with open('configs.json', 'r') as f:
            configs = json.load(f)
            
        # Check if joinleave and guilds sections exist
        if 'joinleave' not in configs or 'guilds' not in configs['joinleave']:
            return None
            
        # Get guild specific channel
        guild_id = str(guild.id)
        if guild_id in configs['joinleave']['guilds']:
            channel_id = configs['joinleave']['guilds'][guild_id]['channel_id']
            return guild.get_channel(channel_id)
            
        # Fall back to default channel if configured
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
    
    # Get configured channel from config file
    channel = get_join_leave_channel(member.guild)
    
    # Fall back to traditional channel finding if config not found
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
    
    # Get configured channel from config file
    channel = get_join_leave_channel(member.guild)
    
    # Fall back to traditional channel finding if config not found
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
    if "fuck" in message.content.lower():
        await message.delete()
        await message.channel.send(f"{message.author.mention} Please don't use that word here.")
        return
    await bot.process_commands(message)

bot.run(TOKEN, log_handler=handler, log_level=logging.DEBUG)