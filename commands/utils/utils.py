import discord
from discord import app_commands
from discord.ext import commands
import datetime
import time
import asyncio
import math
import random

class Utils(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.start_time = datetime.datetime.utcnow()
        self.afk_users = {}
    
    @app_commands.command(name="userinfo", description="Shows information about a user")
    async def userinfo(self, interaction: discord.Interaction, user: discord.Member = None):
        user = user or interaction.user
        embed = discord.Embed(title="User Information", color=user.color)
        embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
        embed.add_field(name="Username", value=user.name, inline=True)
        embed.add_field(name="ID", value=user.id, inline=True)
        embed.add_field(name="Joined At", value=user.joined_at.strftime("%Y-%m-%d %H:%M:%S"), inline=False)
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
        embed.add_field(name="Bot Version", value="1.0.0", inline=True)
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

async def setup(bot: commands.Bot):
    await bot.add_cog(Utils(bot)) 