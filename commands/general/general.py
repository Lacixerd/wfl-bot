import discord
from discord import app_commands
from discord.ext import commands
import datetime
import aiohttp
import io
import re

class General(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.command(name="ping", description="Shows the bot's latency")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"Latency: {round(self.bot.latency * 1000)}ms")

    @app_commands.command(name="avatar", description="Shows a user's avatar")
    async def avatar(self, interaction: discord.Interaction, user: discord.Member = None):
        """Shows a user's avatar"""
        user = user or interaction.user
        
        embed = discord.Embed(
            title=f"{user.name}'s Avatar",
            color=discord.Color.blue()
        )
        
        avatar_url = user.avatar.url if user.avatar else user.default_avatar.url
        embed.set_image(url=avatar_url)
        embed.set_footer(text=f"Requested by {interaction.user.name}")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="botinfo", description="Shows information about the bot")
    async def botinfo(self, interaction: discord.Interaction):
        """Shows information about the bot"""
        bot_user = self.bot.user
        
        # Calculate uptime
        current_time = datetime.datetime.utcnow()
        uptime = current_time - datetime.datetime.fromtimestamp(self.bot.launch_time)
        days, remainder = divmod(int(uptime.total_seconds()), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"
        
        # Get guild count and member count
        guild_count = len(self.bot.guilds)
        member_count = sum(g.member_count for g in self.bot.guilds)
        
        embed = discord.Embed(
            title=f"{bot_user.name} Information",
            description="A multipurpose Discord bot",
            color=discord.Color.blue()
        )
        
        if bot_user.avatar:
            embed.set_thumbnail(url=bot_user.avatar.url)
            
        embed.add_field(name="Bot ID", value=bot_user.id, inline=True)
        embed.add_field(name="Created On", value=f"<t:{int(bot_user.created_at.timestamp())}:F>", inline=True)
        embed.add_field(name="Uptime", value=uptime_str, inline=True)
        embed.add_field(name="Servers", value=guild_count, inline=True)
        embed.add_field(name="Users", value=member_count, inline=True)
        embed.add_field(name="Library", value=f"discord.py {discord.__version__}", inline=True)
        embed.add_field(name="Support", value="[Join Server](https://discord.gg/yourlinkhere)", inline=True)
        
        embed.set_footer(text=f"Requested by {interaction.user.name}")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="channelinfo", description="Shows information about a channel")
    async def channelinfo(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        """Shows information about a channel"""
        channel = channel or interaction.channel
        
        # Get channel type
        channel_type = str(channel.type).replace("_", " ").title()
        
        # Get channel creation time
        created_at = int(channel.created_at.timestamp())
        
        embed = discord.Embed(
            title=f"#{channel.name} Information",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="Channel ID", value=channel.id, inline=True)
        embed.add_field(name="Type", value=channel_type, inline=True)
        embed.add_field(name="Category", value=channel.category.name if channel.category else "None", inline=True)
        embed.add_field(name="Position", value=channel.position, inline=True)
        embed.add_field(name="NSFW", value="Yes" if channel.is_nsfw() else "No", inline=True)
        embed.add_field(name="Created On", value=f"<t:{created_at}:F>", inline=True)
        
        if isinstance(channel, discord.TextChannel):
            embed.add_field(name="Topic", value=channel.topic or "No topic set", inline=False)
            embed.add_field(name="Slowmode", value=f"{channel.slowmode_delay} seconds" if channel.slowmode_delay else "Disabled", inline=True)
        
        embed.set_footer(text=f"Requested by {interaction.user.name}")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="djsdocs", description="Search the discord.js documentation")
    async def djsdocs(self, interaction: discord.Interaction, query: str):
        """Search the discord.js documentation"""
        await interaction.response.defer()
        
        base_url = "https://djsdocs.sorta.moe/v2/embed"
        
        # Create search query
        params = {
            "src": "stable",
            "q": query
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(base_url, params=params) as resp:
                if resp.status != 200:
                    return await interaction.followup.send("Failed to search the documentation.")
                
                data = await resp.json()
                
                if not data:
                    return await interaction.followup.send(f"No results found for `{query}`.")
                
                # Convert to Discord embed
                embed = discord.Embed.from_dict(data)
                embed.set_footer(text=f"Requested by {interaction.user.name}")
                
                await interaction.followup.send(embed=embed)

    @app_commands.command(name="roleinfo", description="Shows information about a role")
    async def roleinfo(self, interaction: discord.Interaction, role: discord.Role):
        """Shows information about a role"""
        # Get role creation time
        created_at = int(role.created_at.timestamp())
        
        # Format permissions
        permissions = []
        for perm, value in role.permissions:
            if value:
                permissions.append(perm.replace("_", " ").title())
        
        # Get members with this role
        member_count = len(role.members)
        
        embed = discord.Embed(
            title=f"{role.name} Information",
            color=role.color
        )
        
        embed.add_field(name="Role ID", value=role.id, inline=True)
        embed.add_field(name="Color", value=f"#{role.color.value:06x}".upper(), inline=True)
        embed.add_field(name="Position", value=role.position, inline=True)
        embed.add_field(name="Mentionable", value="Yes" if role.mentionable else "No", inline=True)
        embed.add_field(name="Hoisted", value="Yes" if role.hoist else "No", inline=True)
        embed.add_field(name="Members", value=member_count, inline=True)
        embed.add_field(name="Created On", value=f"<t:{created_at}:F>", inline=True)
        
        if permissions:
            # Format permissions nicely
            perm_text = ", ".join(permissions)
            if len(perm_text) > 1024:
                perm_text = perm_text[:1021] + "..."
            embed.add_field(name="Key Permissions", value=perm_text, inline=False)
        
        embed.set_footer(text=f"Requested by {interaction.user.name}")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="rolememberinfo", description="Lists members with a specific role")
    async def rolememberinfo(self, interaction: discord.Interaction, role: discord.Role):
        """Lists members with a specific role"""
        members = role.members
        
        if not members:
            return await interaction.response.send_message(f"No members have the role {role.mention}.")
        
        # Sort members by name
        members.sort(key=lambda m: m.name.lower())
        
        embed = discord.Embed(
            title=f"Members with {role.name} Role",
            description=f"Total members: {len(members)}",
            color=role.color
        )
        
        # Create a list of member names
        member_names = [f"{m.name}" for m in members]
        
        # Split into chunks if too many members
        chunks = [member_names[i:i + 20] for i in range(0, len(member_names), 20)]
        
        for i, chunk in enumerate(chunks):
            if i < 5:  # Limit to 5 fields (100 members)
                embed.add_field(name=f"Members {i*20+1}-{i*20+len(chunk)}", value="\n".join(chunk), inline=True)
        
        if len(chunks) > 5:
            embed.add_field(name="Note", value=f"Showing 100/{len(members)} members", inline=False)
        
        embed.set_footer(text=f"Requested by {interaction.user.name}")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="serverav", description="Shows the server's icon")
    async def serverav(self, interaction: discord.Interaction):
        """Shows the server's icon"""
        guild = interaction.guild
        
        if not guild.icon:
            return await interaction.response.send_message("This server doesn't have an icon.")
        
        embed = discord.Embed(
            title=f"{guild.name} Server Icon",
            color=discord.Color.blue()
        )
        
        embed.set_image(url=guild.icon.url)
        embed.set_footer(text=f"Requested by {interaction.user.name}")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="serverinfo", description="Shows information about the server")
    async def serverinfo(self, interaction: discord.Interaction):
        """Shows information about the server"""
        guild = interaction.guild
        
        # Get creation time
        created_at = int(guild.created_at.timestamp())
        
        # Count channels
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories = len(guild.categories)
        
        # Get member counts
        total_members = guild.member_count
        online_members = sum(1 for m in guild.members if m.status != discord.Status.offline) if guild.chunked else "Unknown"
        
        # Get role count
        roles = len(guild.roles) - 1  # Subtract @everyone
        
        # Get boost info
        boost_level = guild.premium_tier
        boosts = guild.premium_subscription_count
        
        embed = discord.Embed(
            title=f"{guild.name} Server Information",
            color=discord.Color.blue()
        )
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        embed.add_field(name="Server ID", value=guild.id, inline=True)
        embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
        embed.add_field(name="Created On", value=f"<t:{created_at}:F>", inline=True)
        
        embed.add_field(name="Members", value=total_members, inline=True)
        embed.add_field(name="Channels", value=f"📝 {text_channels} | 🔊 {voice_channels} | 📁 {categories}", inline=True)
        embed.add_field(name="Roles", value=roles, inline=True)
        
        embed.add_field(name="Boost Level", value=f"Level {boost_level} ({boosts} boosts)", inline=True)
        
        if guild.features:
            features = ", ".join(f.replace("_", " ").title() for f in guild.features)
            embed.add_field(name="Features", value=features, inline=False)
            
        if guild.description:
            embed.add_field(name="Description", value=guild.description, inline=False)
            
        embed.set_footer(text=f"Requested by {interaction.user.name}")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ss", description="Takes a screenshot of a website")
    async def ss(self, interaction: discord.Interaction, url: str):
        """Takes a screenshot of a website"""
        await interaction.response.defer()
        
        # Add https:// if not present
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        # Use a screenshot API
        screenshot_url = f"https://image.thum.io/get/width/1200/crop/800/fullpage/{url}"
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(screenshot_url) as resp:
                    if resp.status != 200:
                        return await interaction.followup.send("Failed to take a screenshot of the website.")
                    
                    image_data = await resp.read()
                    
                    # Create file
                    file = discord.File(io.BytesIO(image_data), filename="screenshot.png")
                    
                    embed = discord.Embed(
                        title="Website Screenshot",
                        description=url,
                        color=discord.Color.blue()
                    )
                    
                    embed.set_image(url="attachment://screenshot.png")
                    embed.set_footer(text=f"Requested by {interaction.user.name}")
                    
                    await interaction.followup.send(embed=embed, file=file)
            except Exception as e:
                await interaction.followup.send(f"An error occurred: {str(e)}")

    @app_commands.command(name="twitter", description="Get information about a Twitter/X user")
    async def twitter(self, interaction: discord.Interaction, username: str):
        """Get information about a Twitter/X user"""
        await interaction.response.defer()
        
        # Clean the username
        username = username.replace("@", "").strip()
        
        # Use Twitter API services
        twitter_url = f"https://api.twitter.com/2/users/by/username/{username}"
        
        # For demonstration purposes, we'll just show a formatted result
        # In practice, you'd need a Twitter API key
        embed = discord.Embed(
            title=f"@{username}",
            description="This command requires Twitter API credentials which are not available.",
            color=discord.Color.blue(),
            url=f"https://twitter.com/{username}"
        )
        
        embed.add_field(name="Note", value="Due to Twitter API changes, this command would require a paid API key.", inline=False)
        embed.add_field(name="Profile Link", value=f"[Click to view profile](https://twitter.com/{username})", inline=False)
        embed.set_footer(text=f"Requested by {interaction.user.name}")
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="whois", description="Shows detailed information about a user")
    async def whois(self, interaction: discord.Interaction, user: discord.Member = None):
        """Shows detailed information about a user"""
        user = user or interaction.user
        
        # Get join position
        join_position = sorted(interaction.guild.members, key=lambda m: m.joined_at or datetime.datetime.now()).index(user) + 1
        
        # Get dates
        created_at = int(user.created_at.timestamp())
        joined_at = int(user.joined_at.timestamp()) if user.joined_at else None
        
        # Get status and activity
        status = str(user.status).title() if hasattr(user, "status") else "Unknown"
        activity = user.activity.name if user.activity else "None"
        
        # Get role list
        roles = [role.mention for role in user.roles if role.name != "@everyone"]
        roles.reverse()  # Highest role first
        
        embed = discord.Embed(
            title=f"User Information - {user.name}",
            color=user.color
        )
        
        embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
        
        embed.add_field(name="User ID", value=user.id, inline=True)
        embed.add_field(name="Nickname", value=user.nick or "None", inline=True)
        embed.add_field(name="Join Position", value=f"{join_position}{'th' if 4 <= join_position % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(join_position % 10, 'th')}", inline=True)
        
        embed.add_field(name="Created On", value=f"<t:{created_at}:F>", inline=True)
        if joined_at:
            embed.add_field(name="Joined On", value=f"<t:{joined_at}:F>", inline=True)
        
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(name="Activity", value=activity, inline=True)
        
        if roles:
            embed.add_field(name=f"Roles [{len(roles)}]", value=" ".join(roles[:10]) + ("..." if len(roles) > 10 else ""), inline=False)
        
        embed.set_footer(text=f"Requested by {interaction.user.name}")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="wikipedia", description="Search Wikipedia for information")
    async def wikipedia(self, interaction: discord.Interaction, query: str):
        """Search Wikipedia for information"""
        await interaction.response.defer()
        
        # Format the query for the API
        search_query = query.replace(" ", "+")
        
        # Wikipedia API endpoint
        api_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{search_query}"
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(api_url) as resp:
                    if resp.status != 200:
                        return await interaction.followup.send(f"No Wikipedia article found for '{query}'.")
                    
                    data = await resp.json()
                    
                    # Extract information
                    title = data.get("title", "Unknown")
                    extract = data.get("extract", "No information available.")
                    url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
                    
                    # Limit extract length
                    if len(extract) > 4000:
                        extract = extract[:4000] + "..."
                    
                    # Get thumbnail if available
                    thumbnail = data.get("thumbnail", {}).get("source", None)
                    
                    embed = discord.Embed(
                        title=title,
                        description=extract,
                        color=discord.Color.blue(),
                        url=url
                    )
                    
                    if thumbnail:
                        embed.set_thumbnail(url=thumbnail)
                        
                    embed.set_footer(text=f"From Wikipedia • Requested by {interaction.user.name}")
                    
                    await interaction.followup.send(embed=embed)
            except Exception as e:
                await interaction.followup.send(f"An error occurred: {str(e)}")

async def setup(bot: commands.Bot):
    await bot.add_cog(General(bot)) 