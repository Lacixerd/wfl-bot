import discord
from discord import app_commands
from discord.ext import commands
import datetime
import time
import asyncio
import math
import random
import json
import os

class Utils(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.start_time = datetime.datetime.utcnow()
        self.afk_users = {}
        self.images_file = 'wflpraiseimages/images.json'
    
    async def load_images(self):
        """Load images from the JSON file"""
        try:
            if not os.path.exists(self.images_file):
                return {"gifs": []}
            with open(self.images_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading images: {e}")
            return {"gifs": []}
            
    async def save_images(self, data):
        """Save images to the JSON file"""
        try:
            os.makedirs(os.path.dirname(self.images_file), exist_ok=True)
            with open(self.images_file, 'w') as f:
                json.dump(data, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving images: {e}")
            return False

    @app_commands.command(name="userinfo", description="Shows information about a user")
    async def userinfo(self, interaction: discord.Interaction, user: discord.Member = None, user_id: str = None):
        """
        Shows information about a user
        
        Parameters
        -----------
        user: The user to get information about
        user_id: User ID to search for if user is not provided
        """
        target_user = None
        
        # If user is provided, use it
        if user:
            target_user = user
        # If user_id is provided, try to find the user by ID
        elif user_id:
            try:
                # Convert string to int
                user_id_int = int(user_id)
                # Try to get member from current guild first
                target_user = interaction.guild.get_member(user_id_int)
                
                # If not found in guild, try to fetch user from Discord
                if not target_user:
                    try:
                        fetched_user = await self.bot.fetch_user(user_id_int)
                        # Create a basic user info embed for non-guild members
                        embed = discord.Embed(title="User Information (Not in this server)", color=discord.Color.blue())
                        embed.set_thumbnail(url=fetched_user.avatar.url if fetched_user.avatar else fetched_user.default_avatar.url)
                        embed.add_field(name="Username", value=fetched_user.name, inline=True)
                        embed.add_field(name="Display Name", value=fetched_user.display_name, inline=True)
                        embed.add_field(name="ID", value=fetched_user.id, inline=True)
                        embed.add_field(name="Created At", value=f"<t:{int(fetched_user.created_at.timestamp())}:F>", inline=False)
                        embed.add_field(name="Bot", value="Yes" if fetched_user.bot else "No", inline=True)
                        embed.set_footer(text="This user is not a member of this server")
                        return await interaction.response.send_message(embed=embed)
                    except discord.NotFound:
                        return await interaction.response.send_message(f"User with ID `{user_id}` not found.", ephemeral=True)
                    except discord.HTTPException:
                        return await interaction.response.send_message("An error occurred while fetching user information.", ephemeral=True)
                        
            except ValueError:
                return await interaction.response.send_message("Invalid user ID. Please provide a valid numerical ID.", ephemeral=True)
        else:
            # If neither user nor user_id is provided, use the command invoker
            target_user = interaction.user
            
        # Create embed for guild member
        embed = discord.Embed(title="User Information", color=target_user.color)
        embed.set_thumbnail(url=target_user.avatar.url if target_user.avatar else target_user.default_avatar.url)
        
        embed.add_field(name="Username", value=target_user.name, inline=True)
        embed.add_field(name="Display Name", value=target_user.display_name, inline=True)
        embed.add_field(name="ID", value=target_user.id, inline=True)
        
        embed.add_field(name="Created At", value=f"<t:{int(target_user.created_at.timestamp())}:F>", inline=False)
        if target_user.joined_at:
            embed.add_field(name="Joined At", value=f"<t:{int(target_user.joined_at.timestamp())}:F>", inline=False)
            
        embed.add_field(name="Bot", value="Yes" if target_user.bot else "No", inline=True)
        
        # Add status if available
        if hasattr(target_user, 'status'):
            status_emojis = {
                discord.Status.online: "🟢",
                discord.Status.idle: "🟡", 
                discord.Status.dnd: "🔴",
                discord.Status.offline: "⚫"
            }
            status_emoji = status_emojis.get(target_user.status, "❓")
            embed.add_field(name="Status", value=f"{status_emoji} {target_user.status.name.title()}", inline=True)
        
        # Add roles if it's a guild member
        if hasattr(target_user, 'roles') and len(target_user.roles) > 1:
            roles = [role.mention for role in target_user.roles if role.name != "@everyone"]
            roles.reverse()  # Highest role first
            if roles:
                roles_text = " ".join(roles[:10])  # Limit to 10 roles to avoid embed limits
                if len(target_user.roles) > 11:  # 10 + @everyone
                    roles_text += f" ... and {len(target_user.roles) - 11} more"
                embed.add_field(name=f"Roles [{len(target_user.roles) - 1}]", value=roles_text, inline=False)
        
        # Add permissions if it's a guild member
        if hasattr(target_user, 'guild_permissions'):
            key_perms = []
            if target_user.guild_permissions.administrator:
                key_perms.append("Administrator")
            elif target_user.guild_permissions.manage_guild:
                key_perms.append("Manage Server")
            elif target_user.guild_permissions.manage_channels:
                key_perms.append("Manage Channels")
            elif target_user.guild_permissions.manage_messages:
                key_perms.append("Manage Messages")
            elif target_user.guild_permissions.kick_members:
                key_perms.append("Kick Members")
            elif target_user.guild_permissions.ban_members:
                key_perms.append("Ban Members")
                
            if key_perms:
                embed.add_field(name="Key Permissions", value=", ".join(key_perms), inline=False)
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="calculate", description="Calculate a mathematical expression")
    async def calculate(self, interaction: discord.Interaction, expression: str):
        """
        Calculate a mathematical expression
        
        Parameters
        -----------
        expression: The mathematical expression to calculate
        """
        try:
            # Evaluate the expression safely
            # Using eval with limited scope to avoid security issues
            allowed_names = {
                'abs': abs, 'round': round, 'min': min, 'max': max,
                'sum': sum, 'pow': pow, 'math': math,
                'sin': math.sin, 'cos': math.cos, 'tan': math.tan,
                'sqrt': math.sqrt, 'pi': math.pi, 'e': math.e
            }
            
            # Replace ^ with ** for power operations
            expression = expression.replace('^', '**')
            
            # Evaluate the expression
            result = eval(expression, {"__builtins__": {}}, allowed_names)
            
            # Format the result
            if isinstance(result, float):
                # Avoid scientific notation for large/small numbers
                if abs(result) > 1e6 or (abs(result) < 1e-6 and result != 0):
                    formatted_result = f"{result:.10g}"
                else:
                    # Remove trailing zeros for decimal numbers
                    formatted_result = f"{result:.10f}".rstrip('0').rstrip('.')
            else:
                formatted_result = str(result)
                
            # Create embed
            embed = discord.Embed(
                title="Calculation Result",
                color=discord.Color.blue()
            )
            embed.add_field(name="Expression", value=f"`{expression}`", inline=False)
            embed.add_field(name="Result", value=f"`{formatted_result}`", inline=False)
            
            await interaction.response.send_message(embed=embed)
            
        except ZeroDivisionError:
            await interaction.response.send_message("Error: Division by zero is not allowed.", ephemeral=True)
        except (SyntaxError, TypeError, ValueError, NameError) as e:
            await interaction.response.send_message(f"Error: Invalid expression. {str(e)}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

    @app_commands.command(name="help", description="Show a list of available commands")
    async def help(self, interaction: discord.Interaction):
        """Show a list of available commands"""
        # Defer the response to avoid timeout errors
        await interaction.response.defer(ephemeral=True)
        
        embed = discord.Embed(
            title="Command List",
            description="Here are all the available commands organized by category.",
            color=discord.Color.blue()
        )
        
        # Group commands by category (cog)
        commands_by_cog = {}
        
        for cmd in self.bot.tree.get_commands():
            # Add all commands without permission checking
            cog_name = getattr(cmd.callback, '__cog_name__', 'Other')
            
            # Komut adına göre kategori belirleyebiliriz
            command_name = cmd.name.lower()
            
            if cog_name == 'Other' or cog_name == 'Uncategorized':
                # Admin komutlar
                if command_name in ['ban', 'kick', 'clear', 'warn', 'mute', 'unmute', 'lock', 'role', 'tempban', 'deletewarn', 'showwarns', 'dm', 'banlist','unban','unrole', 'unlock', 'announce']:
                    cog_name = 'Moderation'
                
                # Moderation komutlar
                elif command_name in ['autorolemessage', 'createrole', 'deleterole', 'modlogset', 'joinleaveset']:
                    cog_name = 'Admin'
                    
                # Genel komutlar
                elif command_name in ['ping', 'userinfo', 'serverinfo', 'avatar', 'botinfo', 'channelinfo', 
                                 'djsdocs', 'roleinfo', 'rolememberinfo', 'serverav', 'ss', 'twitter', 
                                 'whois', 'wikipedia']:
                    cog_name = 'General'
                    
                # Utils komutlar
                elif command_name in ['calculate', 'help', 'invite', 'poll', 'afk', 'setafk',
                                  'removeafk', 'uptime', 'utilsping']:
                    cog_name = 'Utils'
                    
                # Roblox komutlar
                elif command_name in ['robloxprofile', 'robloxgame', 'setuproblox']:
                    cog_name = 'Roblox (Currently not working)'
                    
            if cog_name not in commands_by_cog:
                commands_by_cog[cog_name] = []
            
            commands_by_cog[cog_name].append(cmd)
        
        # Add fields for each category
        for cog_name, cmds in sorted(commands_by_cog.items()):
            if cmds:
                # Sort commands by name and get only command names
                cmd_names = sorted([cmd.name for cmd in cmds])
                
                # Format commands as a comma-separated list
                cmds_text = ", ".join(cmd_names)
                
                # Add emoji based on category name
                emoji = "⚙️"  # Default emoji
                if "admin" in cog_name.lower():
                    emoji = "⚙️"  # Admin
                elif "mod" in cog_name.lower():
                    emoji = "🔧"  # Mod
                elif "utils" in cog_name.lower() or "util" in cog_name.lower():
                    emoji = "🔧"  # Utils
                elif "fun" in cog_name.lower():
                    emoji = "😃"  # Fun
                elif "music" in cog_name.lower():
                    emoji = "🎵"  # Music
                elif "image" in cog_name.lower() or "img" in cog_name.lower():
                    emoji = "🔍"  # Image
                elif "info" in cog_name.lower():
                    emoji = "📚"  # Info
                elif "general" in cog_name.lower():
                    emoji = "📜"  # General
                elif "roblox" in cog_name.lower():
                    emoji = "🎮"  # Games
                
                # Split into chunks if too long (Discord field limit is 1024 chars)
                if len(cmds_text) <= 1000:
                    embed.add_field(
                        name=f"{emoji} {cog_name}",
                        value=f"```{cmds_text}```",
                        inline=False
                    )
                else:
                    # Split text at around 1000 chars at a comma
                    chunks = []
                    current = ""
                    for cmd in cmd_names:
                        if len(current) + len(cmd) + 2 > 1000:  # +2 for comma and space
                            chunks.append(current.rstrip(", "))
                            current = cmd
                        else:
                            current += (cmd + ", ")
                    
                    if current:
                        chunks.append(current.rstrip(", "))
                    
                    # Add each chunk as a field
                    for i, chunk in enumerate(chunks):
                        name = f"{emoji} {cog_name}"
                        if len(chunks) > 1:
                            name += f" ({i+1}/{len(chunks)})"
                        
                        embed.add_field(
                            name=name,
                            value=f"```{chunk}```",
                            inline=False
                        )
        
        embed.set_footer(text="Join the support server for more information: https://discord.gg/ZmTQcbFBVt")
        
        # Send the deferred response
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="invite", description="Get an invite link for the bot")
    async def invite(self, interaction: discord.Interaction):
        """Get an invite link for the bot"""
        # Create a permission integer with common permissions
        # You can customize this as needed
        permissions = discord.Permissions(
            send_messages=True,
            embed_links=True,
            attach_files=True,
            read_messages=True,
            read_message_history=True,
            add_reactions=True,
            use_external_emojis=True,
            manage_messages=True
        )
        
        # Generate the invite URL
        invite_url = discord.utils.oauth_url(
            client_id=self.bot.user.id,
            permissions=permissions,
            scopes=("bot", "applications.commands")
        )
        
        embed = discord.Embed(
            title="Invite Link",
            description=f"Click the link below to add me to your server:",
            color=discord.Color.blue()
        )
        embed.add_field(name="Bot Invite", value=f"[Click Here]({invite_url})", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="utilsping", description="Check the bot's detailed latency")
    async def utilsping(self, interaction: discord.Interaction):
        """Check the bot's detailed latency"""
        # Start time for message round trip
        start_time = time.time()
        
        # Defer the response to measure round-trip time
        await interaction.response.defer(ephemeral=False)
        
        # Calculate round-trip time
        end_time = time.time()
        message_latency = (end_time - start_time) * 1000  # Convert to ms
        
        # Get WebSocket latency
        websocket_latency = self.bot.latency * 1000  # Convert to ms
        
        embed = discord.Embed(
            title="🏓 Pong!",
            color=discord.Color.green()
        )
        
        embed.add_field(name="Bot Latency", value=f"{message_latency:.2f} ms", inline=True)
        embed.add_field(name="WebSocket Latency", value=f"{websocket_latency:.2f} ms", inline=True)
        
        # Add uptime information
        uptime = datetime.datetime.utcnow() - self.start_time
        days, remainder = divmod(uptime.total_seconds(), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        uptime_str = f"{int(days)}d {int(hours)}h {int(minutes)}m {int(seconds)}s"
        embed.add_field(name="Uptime", value=uptime_str, inline=False)
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="poll", description="Create a poll")
    async def poll(
        self, 
        interaction: discord.Interaction, 
        question: str, 
        option1: str, 
        option2: str,
        option3: str = None,
        option4: str = None,
        option5: str = None,
        option6: str = None,
        option7: str = None,
        option8: str = None,
        option9: str = None,
        option10: str = None
    ):
        """
        Create a poll with up to 10 options
        
        Parameters
        -----------
        question: The question for your poll
        option1: First option
        option2: Second option
        option3: Third option (optional)
        option4: Fourth option (optional)
        option5: Fifth option (optional)
        option6: Sixth option (optional)
        option7: Seventh option (optional)
        option8: Eighth option (optional)
        option9: Ninth option (optional)
        option10: Tenth option (optional)
        """
        # Create a list of all provided options
        options = [opt for opt in [option1, option2, option3, option4, option5, 
                                  option6, option7, option8, option9, option10] if opt is not None]
        
        # Emojis for the options (up to 10)
        option_emojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
        
        # Create the embed
        embed = discord.Embed(
            title=f"Poll: {question}",
            description=f"Created by {interaction.user.mention}",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.utcnow()
        )
        
        # Add the options to the embed
        for i, option in enumerate(options):
            embed.add_field(name=f"Option {i+1}", value=f"{option_emojis[i]} {option}", inline=False)
            
        embed.set_footer(text="React with the emojis to vote!")
        
        # Send the embed
        await interaction.response.send_message(embed=embed)
        message = await interaction.original_response()
        
        # Add the reaction emojis
        for i in range(len(options)):
            await message.add_reaction(option_emojis[i])

    @app_commands.command(name="setafk", description="Set your AFK status")
    async def setafk(self, interaction: discord.Interaction, reason: str = "AFK"):
        """
        Set your AFK status
        
        Parameters
        -----------
        reason: Reason for being AFK (optional)
        """
        user_id = interaction.user.id
        guild_id = interaction.guild.id
        
        # Set user as AFK
        if guild_id not in self.afk_users:
            self.afk_users[guild_id] = {}
            
        self.afk_users[guild_id][user_id] = {
            'reason': reason,
            'time': datetime.datetime.utcnow(),
            'name': interaction.user.display_name
        }
        
        # Try to add [AFK] to the user's nickname if possible
        try:
            # Only change nickname if it doesn't already have [AFK]
            if not interaction.user.display_name.startswith('[AFK]'):
                # Truncate nickname if needed to stay within Discord limits
                new_nick = f"[AFK] {interaction.user.display_name}"
                if len(new_nick) > 32:
                    new_nick = new_nick[:32]
                await interaction.user.edit(nick=new_nick)
        except discord.Forbidden:
            # Skip if we don't have permission to change nicknames
            pass
            
        await interaction.response.send_message(f"I've set your AFK status: {reason}", ephemeral=True)

    @app_commands.command(name="removeafk", description="Remove your AFK status")
    async def removeafk(self, interaction: discord.Interaction):
        """Remove your AFK status"""
        user_id = interaction.user.id
        guild_id = interaction.guild.id
        
        # Check if user is AFK
        if (guild_id in self.afk_users and 
            user_id in self.afk_users[guild_id]):
            
            # Remove AFK status
            afk_data = self.afk_users[guild_id].pop(user_id)
            
            # Calculate AFK duration
            afk_time = afk_data['time']
            current_time = datetime.datetime.utcnow()
            delta = current_time - afk_time
            
            # Format duration
            hours, remainder = divmod(delta.total_seconds(), 3600)
            minutes, seconds = divmod(remainder, 60)
            
            if hours > 0:
                duration = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
            elif minutes > 0:
                duration = f"{int(minutes)}m {int(seconds)}s"
            else:
                duration = f"{int(seconds)}s"
                
            # Try to remove [AFK] from user's nickname
            try:
                if interaction.user.display_name.startswith('[AFK]'):
                    # Get original name (stored or from current nickname)
                    original_name = afk_data.get('name', interaction.user.display_name[5:].strip())
                    await interaction.user.edit(nick=original_name)
            except discord.Forbidden:
                # Skip if we don't have permission
                pass
                
            await interaction.response.send_message(f"Welcome back! You were AFK for {duration}.", ephemeral=True)
        else:
            await interaction.response.send_message("You are not currently AFK.", ephemeral=True)

    @app_commands.command(name="uptime", description="Check how long the bot has been online")
    async def uptime(self, interaction: discord.Interaction):
        """Check how long the bot has been online"""
        current_time = datetime.datetime.utcnow()
        uptime = current_time - self.start_time
        
        # Calculate the uptime components
        days, remainder = divmod(uptime.total_seconds(), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        # Create embed
        embed = discord.Embed(
            title="Bot Uptime",
            color=discord.Color.green(),
            timestamp=current_time
        )
        
        # Format uptime string
        uptime_str = ""
        if days > 0:
            uptime_str += f"{int(days)} day{'s' if days != 1 else ''}, "
        if hours > 0 or days > 0:
            uptime_str += f"{int(hours)} hour{'s' if hours != 1 else ''}, "
        if minutes > 0 or hours > 0 or days > 0:
            uptime_str += f"{int(minutes)} minute{'s' if minutes != 1 else ''}, "
        uptime_str += f"{int(seconds)} second{'s' if seconds != 1 else ''}"
        
        embed.add_field(name="Online For", value=uptime_str, inline=False)
        embed.add_field(name="Started At", value=f"<t:{int(self.start_time.timestamp())}:F>", inline=False)
        
        # Add bot version and other optional details
        embed.add_field(name="Bot Version", value="2.1.0", inline=True)
        embed.add_field(name="Discord.py Version", value=discord.__version__, inline=True)
        
        await interaction.response.send_message(embed=embed)
        
    @commands.Cog.listener()
    async def on_message(self, message):
        # Skip if it's a bot message
        if message.author.bot:
            return
            
        # Skip if not in a guild (DM)
        if not message.guild:
            return
            
        guild_id = message.guild.id
        
        # Check if the guild has any AFK users
        if guild_id not in self.afk_users:
            return
            
        author_id = message.author.id
        
        # Check if author is AFK and remove status if they send a message
        if author_id in self.afk_users[guild_id]:
            # Remove AFK status
            afk_data = self.afk_users[guild_id].pop(author_id)
            
            # Calculate AFK duration
            afk_time = afk_data['time']
            current_time = datetime.datetime.utcnow()
            delta = current_time - afk_time
            
            # Format duration
            hours, remainder = divmod(delta.total_seconds(), 3600)
            minutes, seconds = divmod(remainder, 60)
            
            if hours > 0:
                duration = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
            elif minutes > 0:
                duration = f"{int(minutes)}m {int(seconds)}s"
            else:
                duration = f"{int(seconds)}s"
                
            # Try to remove [AFK] from user's nickname
            try:
                if message.author.display_name.startswith('[AFK]'):
                    # Get original name from stored data or strip [AFK] prefix
                    original_name = afk_data.get('name', message.author.display_name[5:].strip())
                    await message.author.edit(nick=original_name)
            except discord.Forbidden:
                # Skip if we don't have permission
                pass
                
            await message.channel.send(f"{message.author.mention}, welcome back! You were AFK for {duration}.", delete_after=10)
            
        # Check for mentions of AFK users
        for user_id, user_data in list(self.afk_users.get(guild_id, {}).items()):
            if user_id == author_id:
                continue  # Skip, we already handled this above
                
            # Check if the author mentioned an AFK user
            user = message.guild.get_member(user_id)
            if user and (user.mentioned_in(message) or f"<@{user_id}>" in message.content or f"<@!{user_id}>" in message.content):
                # Calculate how long they've been AFK
                afk_time = user_data['time']
                current_time = datetime.datetime.utcnow()
                delta = current_time - afk_time
                
                # Format duration
                hours, remainder = divmod(delta.total_seconds(), 3600)
                minutes, seconds = divmod(remainder, 60)
                
                if hours > 0:
                    duration = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
                elif minutes > 0:
                    duration = f"{int(minutes)}m {int(seconds)}s"
                else:
                    duration = f"{int(seconds)}s"
                    
                # Send notification
                await message.channel.send(
                    f"{message.author.mention}, {user.mention} is AFK: {user_data['reason']} - {duration} ago",
                    delete_after=10
                )

    @app_commands.command(name="wafflepraise", description="Special gifs and images for waffle lovers!")
    async def wafflepraise(self, interaction: discord.Interaction):
        """Sends a random waffle gif or image"""
        # Load images from JSON
        data = await self.load_images()
        if not data["gifs"]:
            return await interaction.response.send_message("No waffle gifs available!", ephemeral=True)
            
        await interaction.response.send_message(random.choice(data["gifs"]))

    @app_commands.command(name="addwafflegifs", description="Add new waffle gifs to the collection")
    @app_commands.default_permissions(administrator=True)
    async def addwafflegifs(self, interaction: discord.Interaction, urls: str):
        """
        Add new waffle gifs to the collection
        
        Parameters
        -----------
        urls: Space-separated URLs of gifs/images to add
        """
        # Check if user is administrator
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("You need Administrator permission to use this command!", ephemeral=True)
            
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Load current images
            data = await self.load_images()
            
            # Split URLs and remove empty strings
            new_urls = [url.strip() for url in urls.split() if url.strip()]
            
            if not new_urls:
                return await interaction.followup.send("No valid URLs provided!", ephemeral=True)
                
            # Add new URLs
            added_urls = []
            skipped_urls = []
            
            for url in new_urls:
                if url not in data["gifs"]:
                    data["gifs"].append(url)
                    added_urls.append(url)
                else:
                    skipped_urls.append(url)
                    
            # Save updated data only if we added new URLs
            if added_urls:
                success = await self.save_images(data)
                if not success:
                    return await interaction.followup.send("An error occurred while saving the images.", ephemeral=True)
                    
            # Create response embed
            embed = discord.Embed(
                title="Waffle Gifs Update",
                color=discord.Color.green() if added_urls else discord.Color.orange()
            )
            
            if added_urls:
                embed.add_field(
                    name="✅ Added URLs",
                    value="\n".join(added_urls) if len("\n".join(added_urls)) <= 1024 else f"{len(added_urls)} URLs added",
                    inline=False
                )
            
            if skipped_urls:
                embed.add_field(
                    name="⚠️ Already Existing URLs",
                    value="\n".join(skipped_urls) if len("\n".join(skipped_urls)) <= 1024 else f"{len(skipped_urls)} URLs skipped",
                    inline=False
                )
                
            embed.add_field(name="📊 Total Gifs", value=str(len(data["gifs"])), inline=False)
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)

    @app_commands.command(name="giflist", description="List all waffle gifs in the collection")
    @app_commands.default_permissions(administrator=True)
    async def giflist(self, interaction: discord.Interaction):
        """List all waffle gifs in the collection"""
        # Check if user is administrator
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("You need Administrator permission to use this command!", ephemeral=True)
            
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Load images
            data = await self.load_images()
            
            if not data["gifs"]:
                return await interaction.followup.send("No waffle gifs in the collection!", ephemeral=True)
                
            # Create embed pages (max 10 URLs per page)
            urls = data["gifs"]
            urls_per_page = 10
            pages = []
            
            for i in range(0, len(urls), urls_per_page):
                page_urls = urls[i:i + urls_per_page]
                
                embed = discord.Embed(
                    title="Waffle Gifs List",
                    description=f"Page {len(pages) + 1}/{(len(urls) + urls_per_page - 1) // urls_per_page}",
                    color=discord.Color.blue()
                )
                
                for j, url in enumerate(page_urls, start=i+1):
                    embed.add_field(
                        name=f"#{j}",
                        value=url,
                        inline=False
                    )
                    
                embed.set_footer(text=f"Total Gifs: {len(urls)}")
                pages.append(embed)
                
            # Send first page
            if len(pages) == 1:
                await interaction.followup.send(embed=pages[0], ephemeral=True)
            else:
                # Add navigation buttons for multiple pages
                current_page = 0
                
                view = discord.ui.View(timeout=300)  # 5 minutes timeout
                
                # Previous page button
                prev_button = discord.ui.Button(
                    label="◀️ Previous",
                    style=discord.ButtonStyle.gray,
                    custom_id="prev",
                    disabled=True
                )
                
                # Next page button
                next_button = discord.ui.Button(
                    label="Next ▶️",
                    style=discord.ButtonStyle.gray,
                    custom_id="next",
                    disabled=len(pages) <= 1
                )
                
                # Page indicator
                page_indicator = discord.ui.Button(
                    label=f"Page 1/{len(pages)}",
                    style=discord.ButtonStyle.gray,
                    disabled=True
                )
                
                view.add_item(prev_button)
                view.add_item(page_indicator)
                view.add_item(next_button)
                
                message = await interaction.followup.send(embed=pages[0], view=view, ephemeral=True)
                
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)

    @app_commands.command(name="removegifurl", description="Remove a gif URL from the collection")
    @app_commands.default_permissions(administrator=True)
    async def removegifurl(self, interaction: discord.Interaction, url: str):
        """
        Remove a gif URL from the collection
        
        Parameters
        -----------
        url: The URL to remove
        """
        # Check if user is administrator
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("You need Administrator permission to use this command!", ephemeral=True)
            
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Load images
            data = await self.load_images()
            
            if not data["gifs"]:
                return await interaction.followup.send("No waffle gifs in the collection!", ephemeral=True)
                
            # Check if URL exists
            if url not in data["gifs"]:
                return await interaction.followup.send("This URL is not in the collection!", ephemeral=True)
                
            # Remove URL
            data["gifs"].remove(url)
            
            # Save updated data
            success = await self.save_images(data)
            if not success:
                return await interaction.followup.send("An error occurred while saving the changes.", ephemeral=True)
                
            # Create response embed
            embed = discord.Embed(
                title="Waffle Gif Removed",
                description="The URL has been removed from the collection.",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="Removed URL",
                value=url,
                inline=False
            )
            
            embed.add_field(
                name="Remaining Gifs",
                value=str(len(data["gifs"])),
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """Event listener for button interactions"""
        if not interaction.data or not interaction.data.get('custom_id'):
            return
            
        custom_id = interaction.data['custom_id']
        
        # Handle giflist pagination
        if custom_id in ['prev', 'next'] and interaction.message:
            try:
                # Get current embed
                current_embed = interaction.message.embeds[0]
                
                # Get current page number
                current_page = int(current_embed.description.split()[1]) - 1
                total_pages = int(current_embed.description.split('/')[-1])
                
                # Load all gifs
                data = await self.load_images()
                urls = data["gifs"]
                urls_per_page = 10
                
                # Calculate new page number
                if custom_id == 'prev':
                    new_page = max(0, current_page - 1)
                else:  # next
                    new_page = min(total_pages - 1, current_page + 1)
                    
                # Create new embed for the page
                new_embed = discord.Embed(
                    title="Waffle Gifs List",
                    description=f"Page {new_page + 1}/{total_pages}",
                    color=discord.Color.blue()
                )
                
                # Add URLs for the new page
                start_idx = new_page * urls_per_page
                page_urls = urls[start_idx:start_idx + urls_per_page]
                
                for i, url in enumerate(page_urls, start=start_idx+1):
                    new_embed.add_field(
                        name=f"#{i}",
                        value=url,
                        inline=False
                    )
                    
                new_embed.set_footer(text=f"Total Gifs: {len(urls)}")
                
                # Update button states
                view = discord.ui.View(timeout=300)
                
                prev_button = discord.ui.Button(
                    label="◀️ Previous",
                    style=discord.ButtonStyle.gray,
                    custom_id="prev",
                    disabled=(new_page == 0)
                )
                
                next_button = discord.ui.Button(
                    label="Next ▶️",
                    style=discord.ButtonStyle.gray,
                    custom_id="next",
                    disabled=(new_page == total_pages - 1)
                )
                
                page_indicator = discord.ui.Button(
                    label=f"Page {new_page + 1}/{total_pages}",
                    style=discord.ButtonStyle.gray,
                    disabled=True
                )
                
                view.add_item(prev_button)
                view.add_item(page_indicator)
                view.add_item(next_button)
                
                # Update the message
                await interaction.response.edit_message(embed=new_embed, view=view)
                
            except Exception as e:
                await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)
                
        # Handle other button interactions from existing handlers
        elif custom_id.startswith('autorole_'):
            # ... existing autorole handler code ...
            pass
        elif custom_id.startswith('permissions_'):
            # ... existing permissions handler code ...
            pass
        elif custom_id.startswith('save_perms_'):
            # ... existing save_perms handler code ...
            pass
        elif custom_id.startswith('delete_role_'):
            # ... existing delete_role handler code ...
            pass
        elif custom_id.startswith('unlock_'):
            # ... existing unlock handler code ...
            pass
        elif custom_id.startswith('banlist_'):
            # ... existing banlist handler code ...
            pass

async def setup(bot: commands.Bot):
    await bot.add_cog(Utils(bot)) 