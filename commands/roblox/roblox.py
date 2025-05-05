import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import json
import os
import asyncio

class Roblox(commands.Cog):
    """Roblox integration commands"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # API endpoints - HTTPS olarak tam URL'ler
        self.api_base = "https://api.roblox.com"
        self.users_api = "https://users.roblox.com/v1"
        self.thumbnails_api = "https://thumbnails.roblox.com/v1"
        self.games_api = "https://games.roblox.com/v1"
        # Config
        self.config_file = 'configs.json'
        # Timeout settings
        self.timeout = aiohttp.ClientTimeout(total=15)  # 15 saniye toplam timeout
        
    async def get_roblox_config(self):
        """Get Roblox configuration from config file"""
        if not os.path.exists(self.config_file):
            return {}
            
        try:
            with open(self.config_file, 'r') as f:
                configs = json.load(f)
                
            # Initialize roblox section if not exists
            if 'roblox' not in configs:
                configs['roblox'] = {}
                
            return configs.get('roblox', {})
        except Exception as e:
            print(f"Error loading Roblox config: {e}")
            return {}
            
    async def save_roblox_config(self, config_data):
        """Save Roblox configuration to config file"""
        try:
            # Create configs directory if it doesn't exist
            os.makedirs('configs', exist_ok=True)
            
            # Load existing config
            configs = {}
            if os.path.exists(self.config_file):
                try:
                    with open(self.config_file, 'r') as f:
                        configs = json.load(f)
                except json.JSONDecodeError:
                    configs = {}
            
            # Update roblox section
            configs['roblox'] = config_data
            
            # Save the config
            with open(self.config_file, 'w') as f:
                json.dump(configs, f, indent=4)
                
            return True
        except Exception as e:
            print(f"Error saving Roblox config: {e}")
            return False
    
    async def fetch_roblox_user(self, username):
        """Fetch Roblox user by username"""
        try:
            print(f"Fetching Roblox user: {username}")
            # Default connectors ile ve timeout ayarlı bağlantı
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                url = f"{self.api_base}/users/get-by-username?username={username}"
                print(f"Request URL: {url}")
                
                async with session.get(url) as response:
                    print(f"Response status: {response.status}")
                    if response.status == 200:
                        data = await response.json()
                        if data.get('success', True) is False:
                            print(f"API success is false: {data}")
                            return None
                        print(f"User data received: {data}")
                        return data
                    else:
                        print(f"Error status code: {response.status}")
                        error_text = await response.text()
                        print(f"Error content: {error_text}")
                        return None
        except Exception as e:
            print(f"Error fetching Roblox user: {e}")
            import traceback
            traceback.print_exc()
            return None
            
    async def fetch_user_avatar(self, user_id):
        """Fetch user avatar thumbnail"""
        try:
            print(f"Fetching avatar for user ID: {user_id}")
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                url = f"{self.thumbnails_api}/users/avatar-headshot?userIds={user_id}&size=420x420&format=Png"
                print(f"Avatar URL: {url}")
                
                async with session.get(url) as response:
                    print(f"Avatar response status: {response.status}")
                    if response.status == 200:
                        data = await response.json()
                        image_url = data.get('data', [{}])[0].get('imageUrl')
                        print(f"Avatar URL received: {image_url}")
                        return image_url
                    else:
                        error_text = await response.text()
                        print(f"Avatar error: {error_text}")
                        return None
        except Exception as e:
            print(f"Error fetching avatar: {e}")
            return None
    
    @app_commands.command(name="robloxprofile", description="Get information about a Roblox user")
    @app_commands.guild_only()
    async def robloxprofile(
        self, 
        interaction: discord.Interaction, 
        username: str
    ):
        """
        Get information about a Roblox user
        
        Parameters
        -----------
        username: The Roblox username to look up
        """
        await interaction.response.defer()
        print(f"Roblox profile command initiated for username: {username}")
        
        # Fetch user data
        user_data = await self.fetch_roblox_user(username)
        
        if not user_data or 'Id' not in user_data:
            print(f"Could not find Roblox user: {username}")
            return await interaction.followup.send(f"Could not find Roblox user: {username}", ephemeral=True)
            
        user_id = user_data.get('Id')
        print(f"Found user ID: {user_id}")
        
        # Fetch avatar
        avatar_url = await self.fetch_user_avatar(user_id)
        
        # Create embed
        embed = discord.Embed(
            title=f"Roblox Profile: {user_data.get('Username')}",
            color=discord.Color.from_rgb(226, 35, 26),  # Roblox red
            url=f"https://www.roblox.com/users/{user_id}/profile"
        )
        
        embed.add_field(name="Display Name", value=user_data.get('DisplayName', 'N/A'), inline=True)
        embed.add_field(name="User ID", value=user_id, inline=True)
        
        if avatar_url:
            embed.set_thumbnail(url=avatar_url)
            
        embed.set_footer(text="Data from Roblox API")
        
        # Fetch additional user info if possible
        try:
            print(f"Fetching additional user info for ID: {user_id}")
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                url = f"{self.users_api}/users/{user_id}"
                print(f"User info URL: {url}")
                
                async with session.get(url) as response:
                    print(f"User info response status: {response.status}")
                    if response.status == 200:
                        user_info = await response.json()
                        print(f"Additional user info received")
                        
                        # Add creation date
                        if 'created' in user_info:
                            print(f"Account creation date: {user_info.get('created')}")
                            # Convert to timestamp for Discord to format locally
                            created_date = user_info.get('created').replace('Z', '+00:00')
                            import datetime
                            try:
                                created_timestamp = int(datetime.datetime.fromisoformat(created_date).timestamp())
                                embed.add_field(
                                    name="Account Created", 
                                    value=f"<t:{created_timestamp}:F>", 
                                    inline=False
                                )
                            except Exception as e:
                                print(f"Error parsing date: {e}")
                                embed.add_field(name="Account Created", value=user_info.get('created'), inline=False)
                        
                        # Add description if available
                        if 'description' in user_info and user_info.get('description'):
                            description = user_info.get('description')
                            # Truncate if too long
                            if len(description) > 1000:
                                description = description[:997] + "..."
                            embed.add_field(name="Description", value=description, inline=False)
        except Exception as e:
            print(f"Error fetching additional user info: {e}")
            import traceback
            traceback.print_exc()
        
        print("Sending profile embed")
        await interaction.followup.send(embed=embed)
        
    @app_commands.command(name="setuproblox", description="Set up Roblox integration settings")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def setuproblox(
        self, 
        interaction: discord.Interaction,
        api_key: str = None,
        verification_channel: discord.TextChannel = None
    ):
        """
        Set up Roblox integration settings
        
        Parameters
        -----------
        api_key: Optional API key for Roblox API
        verification_channel: Channel for verification requests
        """
        # Check if user has administrator permission
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("You must have the 'Administrator' permission to use this command.", ephemeral=True)
            
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get current config
            config = await self.get_roblox_config()
            
            # Initialize guild config if not exists
            guild_id = str(interaction.guild.id)
            if 'guilds' not in config:
                config['guilds'] = {}
                
            if guild_id not in config['guilds']:
                config['guilds'][guild_id] = {}
                
            guild_config = config['guilds'][guild_id]
            
            # Update API key if provided
            if api_key:
                guild_config['api_key'] = api_key
                
            # Update verification channel if provided
            if verification_channel:
                guild_config['verification_channel'] = {
                    'id': verification_channel.id,
                    'name': verification_channel.name
                }
                
            # Save the config
            await self.save_roblox_config(config)
            
            # Create success embed
            embed = discord.Embed(
                title="Roblox Integration Setup",
                description="Roblox integration settings have been updated.",
                color=discord.Color.green()
            )
            
            if api_key:
                embed.add_field(name="API Key", value="✅ API Key has been set", inline=True)
                
            if verification_channel:
                embed.add_field(
                    name="Verification Channel", 
                    value=f"Set to {verification_channel.mention}",
                    inline=True
                )
                
            embed.set_footer(text="You can update these settings at any time")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)

    @app_commands.command(name="robloxgame", description="Get information about a Roblox game")
    @app_commands.guild_only()
    async def robloxgame(
        self, 
        interaction: discord.Interaction, 
        game_id: int
    ):
        """
        Get information about a Roblox game
        
        Parameters
        -----------
        game_id: The Roblox game ID to look up
        """
        await interaction.response.defer()
        print(f"Roblox game command initiated for game ID: {game_id}")
        
        try:
            # Fetch game data
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                url = f"https://games.roblox.com/v1/games?universeIds={game_id}"
                print(f"Game URL: {url}")
                
                async with session.get(url) as response:
                    print(f"Game response status: {response.status}")
                    if response.status == 200:
                        game_data = await response.json()
                        data = game_data.get('data', [])
                        
                        if not data:
                            return await interaction.followup.send(f"Could not find Roblox game with ID: {game_id}", ephemeral=True)
                            
                        game = data[0]
                        
                        # Create embed
                        embed = discord.Embed(
                            title=f"Roblox Game: {game.get('name')}",
                            description=game.get('description', 'No description available.'),
                            color=discord.Color.from_rgb(226, 35, 26),  # Roblox red
                            url=f"https://www.roblox.com/games/{game_id}"
                        )
                        
                        # Add game details
                        embed.add_field(name="Creator", value=game.get('creator', {}).get('name', 'Unknown'), inline=True)
                        embed.add_field(name="Playing", value=f"{game.get('playing', 0):,}", inline=True)
                        embed.add_field(name="Visits", value=f"{game.get('visits', 0):,}", inline=True)
                        embed.add_field(name="Created", value=game.get('created', 'Unknown'), inline=True)
                        embed.add_field(name="Updated", value=game.get('updated', 'Unknown'), inline=True)
                        embed.add_field(name="Max Players", value=game.get('maxPlayers', 0), inline=True)
                        
                        # Add thumbnail if possible
                        try:
                            async with session.get(f"https://thumbnails.roblox.com/v1/games/icons?universeIds={game_id}&size=512x512&format=Png") as thumb_response:
                                if thumb_response.status == 200:
                                    thumb_data = await thumb_response.json()
                                    thumb_url = thumb_data.get('data', [{}])[0].get('imageUrl')
                                    if thumb_url:
                                        embed.set_thumbnail(url=thumb_url)
                        except Exception as e:
                            print(f"Error fetching game thumbnail: {e}")
                            
                        embed.set_footer(text="Data from Roblox API")
                        
                        await interaction.followup.send(embed=embed)
                    else:
                        await interaction.followup.send(f"Error getting game data. Status code: {response.status}", ephemeral=True)
        except Exception as e:
            print(f"Error fetching game info: {e}")
            import traceback
            traceback.print_exc()
            await interaction.followup.send(f"An error occurred while fetching game information: {str(e)}", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Roblox(bot)) 