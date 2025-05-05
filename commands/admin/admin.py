import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import datetime
import re
import math
import json
import os

class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.command(name="clear", description="Clear messages from the channel")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear(self, interaction: discord.Interaction, amount: int):
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"Deleted {len(deleted)} messages.", ephemeral=True)

    @app_commands.command(name="role", description="Add a role to a user")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def role(self, interaction: discord.Interaction, user: discord.Member, role: discord.Role):
        # Check if the bot has permission to manage roles
        if not interaction.guild.me.guild_permissions.manage_roles:
            await interaction.response.send_message("Bot has no permission to manage roles.", ephemeral=True)
            return
            
        # Check if the user has permission to manage roles
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("You must have the 'Manage Roles' permission to use this command.", ephemeral=True)
            return
            
        # Check if the role can be assigned
        if role.position >= interaction.guild.me.top_role.position:
            await interaction.response.send_message(f"Bot cannot assign a role higher than its own ({role.mention}).", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)
        try:
            await user.add_roles(role)
            
            embed = discord.Embed(
                title="Role Added",
                description=f"**{role.name}** role has been added to **{user.display_name}**.",
                color=role.color
            )
            embed.add_field(name="Moderator", value=f"{interaction.user.mention}", inline=True)
            embed.add_field(name="Date", value=f"<t:{int(discord.utils.utcnow().timestamp())}:F>", inline=True)
            embed.set_footer(text=f"ID: {user.id}")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("A permission error occurred.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)

    @app_commands.command(name="unrole", description="Remove a role from a user")
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.guild_only()
    async def unrole(self, interaction: discord.Interaction, user: discord.Member, role: discord.Role):
        # Check if the bot has permission to manage roles
        if not interaction.guild.me.guild_permissions.manage_roles:
            return await interaction.response.send_message("Bot has no permission to manage roles.", ephemeral=True)
        
        # Check if the bot can remove roles higher than its own
        if role.position >= interaction.guild.me.top_role.position:
            return await interaction.response.send_message(f"Bot cannot remove a role higher than its own ({role.mention}).", ephemeral=True)
        
        # Check if the user has the role
        if role not in user.roles:
            return await interaction.response.send_message(f"{user.mention} doesn't have the {role.mention} role.", ephemeral=True)
        
        # Check if the user trying to remove the role is higher in the hierarchy
        if user != interaction.user and user.top_role.position >= interaction.user.top_role.position:
            return await interaction.response.send_message(f"You cannot remove a role from someone with higher authority than you.", ephemeral=True)
        
        # Protection for special roles
        if role.is_integration() or role.is_premium_subscriber() or role.is_bot_managed():
            return await interaction.response.send_message(f"{role.mention} is a special role and cannot be removed.", ephemeral=True)
        
        try:
            await interaction.response.defer(ephemeral=True)
            await user.remove_roles(role)
            embed = discord.Embed(
                title="Role Removed",
                description=f"**{role.name}** role has been removed from **{user.display_name}**.",
                color=discord.Color.orange()
            )
            embed.add_field(name="Moderator", value=f"{interaction.user.mention}", inline=True)
            embed.add_field(name="Date", value=f"<t:{int(discord.utils.utcnow().timestamp())}:F>", inline=True)
            embed.set_footer(text=f"ID: {user.id}")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Send DM to the user
            try:
                dm_embed = discord.Embed(
                    title="Role Removed",
                    description=f"Your **{role.name}** role has been removed in **{interaction.guild.name}**.",
                    color=discord.Color.orange()
                )
                await user.send(embed=dm_embed)
            except:
                # Skip if DM can't be sent
                pass
                
        except discord.Forbidden:
            await interaction.followup.send("A permission error occurred while removing the role.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)

    @app_commands.command(name="createrole", description="Create a customizable role")
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.guild_only()
    async def createrole(
        self, 
        interaction: discord.Interaction, 
        name: str,
        color: str = None,
        hoist: bool = False,
        mentionable: bool = False,
        icon: discord.Attachment = None,
        reason: str = None,
        permissions: str = None
    ):
        """
        Create a customizable role
        
        Parameters
        -----------
        name: Role name
        color: Color (hex code e.g., #FF5733 or name e.g., red, blue, green)
        hoist: Whether to display the role separately in the member list
        mentionable: Whether everyone can mention this role
        icon: Role icon (optional)
        reason: Reason to show in the audit log
        permissions: Space-separated list of permissions (e.g., "send_messages read_messages")
        """
        await interaction.response.defer(ephemeral=True)
        
        # Check if the bot has permission to manage roles
        if not interaction.guild.me.guild_permissions.manage_roles:
            return await interaction.followup.send("Bot has no permission to manage roles.", ephemeral=True)
        
        # Check role limit
        if len(interaction.guild.roles) >= 250:
            return await interaction.followup.send("This server has reached the maximum number of roles (250).", ephemeral=True)
        
        # Process color
        role_color = discord.Color.default()
        if color:
            try:
                # Check hex code (#FF5733 format)
                if color.startswith('#'):
                    color = color[1:]  # Remove # symbol
                    
                if len(color) == 6:
                    # Convert hex to int
                    role_color = discord.Color(int(color, 16))
                else:
                    # Check standard color names
                    color_map = {
                        "red": discord.Color.red(),
                        "green": discord.Color.green(),
                        "blue": discord.Color.blue(),
                        "yellow": discord.Color.yellow(),
                        "orange": discord.Color(0xFFA500),
                        "purple": discord.Color.purple(),
                        "black": discord.Color(0x000000),
                        "white": discord.Color(0xFFFFFF),
                        "pink": discord.Color(0xFFC0CB),
                        "cyan": discord.Color(0x00FFFF),
                        "brown": discord.Color(0x8B4513),
                        "gray": discord.Color(0x808080),
                        "gold": discord.Color(0xFFD700),
                        "silver": discord.Color(0xC0C0C0),
                        "teal": discord.Color.teal(),
                        "magenta": discord.Color(0xFF00FF),
                    }
                    
                    if color.lower() in color_map:
                        role_color = color_map[color.lower()]
                    else:
                        return await interaction.followup.send(
                            f"Invalid color format. Use a hex code (#FF5733) or one of these colors: "
                            f"{', '.join(color_map.keys())}", 
                            ephemeral=True
                        )
            except ValueError:
                return await interaction.followup.send("Invalid color format. Use a hex code (#FF5733).", ephemeral=True)
        
        # Process icon
        icon_bytes = None
        if icon:
            # Check file size
            if icon.size > 256 * 1024:  # 256 KB
                return await interaction.followup.send("Icon file is too large. Maximum size is 256 KB.", ephemeral=True)
            
            # Check file type
            if icon.content_type not in ['image/jpeg', 'image/png', 'image/gif']:
                return await interaction.followup.send("Icon file must be JPEG, PNG, or GIF format.", ephemeral=True)
            
            icon_bytes = await icon.read()
        
        # Process permissions
        role_permissions = discord.Permissions.none()
        permission_names = []
        
        if permissions:
            # Split the permissions string into a list
            perm_list = permissions.lower().split()
            
            # Map of permission names to their attributes
            permission_map = {
                "admin": "administrator",
                "administrator": "administrator",
                "manage_server": "manage_guild",
                "manage_channels": "manage_channels",
                "manage_roles": "manage_roles",
                "manage_messages": "manage_messages",
                "kick": "kick_members",
                "ban": "ban_members",
                "invite": "create_instant_invite",
                "change_nickname": "change_nickname",
                "manage_nicknames": "manage_nicknames",
                "manage_webhooks": "manage_webhooks",
                "manage_emojis": "manage_emojis_and_stickers",
                "view_channels": "view_channel",
                "send_messages": "send_messages",
                "send_tts": "send_tts_messages",
                "embed_links": "embed_links",
                "attach_files": "attach_files",
                "read_history": "read_message_history",
                "mention_everyone": "mention_everyone",
                "external_emojis": "use_external_emojis",
                "view_guild_insights": "view_guild_insights",
                "connect": "connect",
                "speak": "speak",
                "mute_members": "mute_members",
                "deafen_members": "deafen_members",
                "move_members": "move_members",
                "use_voice_activity": "use_voice_activation",
                "priority_speaker": "priority_speaker",
                "stream": "stream",
                "read_messages": "read_messages",
                "use_slash_commands": "use_application_commands",
                "manage_threads": "manage_threads",
                "create_public_threads": "create_public_threads",
                "create_private_threads": "create_private_threads",
                "external_stickers": "use_external_stickers",
                "send_messages_in_threads": "send_messages_in_threads",
                "moderate_members": "moderate_members",
            }
            
            # Set permissions based on the provided list
            for perm in perm_list:
                if perm in permission_map:
                    setattr(role_permissions, permission_map[perm], True)
                    permission_names.append(perm)
                elif hasattr(discord.Permissions, perm):
                    setattr(role_permissions, perm, True)
                    permission_names.append(perm)
        
        # Create role
        try:
            role = await interaction.guild.create_role(
                name=name,
                permissions=role_permissions,
                color=role_color,
                hoist=hoist,
                mentionable=mentionable,
                reason=f"{interaction.user.name}: {reason}" if reason else f"Created by {interaction.user.name}"
            )
            
            # Add icon (if provided)
            if icon_bytes:
                try:
                    await role.edit(display_icon=icon_bytes)
                except discord.HTTPException:
                    await interaction.followup.send("Role created but there was an error adding the icon.", ephemeral=True)
                    
            # Set position - default to just below the bot's role
            try:
                my_position = interaction.guild.me.top_role.position - 1
                if my_position > 0:  # If higher than the bottom role (@everyone)
                    await role.edit(position=my_position)
            except discord.HTTPException:
                # Position couldn't be set, but that's ok
                pass
            
            # Success message
            embed = discord.Embed(
                title="Role Created",
                description=f"**{role.name}** role has been created successfully.",
                color=role_color
            )
            
            embed.add_field(name="Hoisted", value="Yes" if hoist else "No", inline=True)
            embed.add_field(name="Mentionable", value="Yes" if mentionable else "No", inline=True)
            embed.add_field(name="Color", value=f"#{role_color.value:06x}".upper(), inline=True)
            
            if permission_names:
                embed.add_field(name="Permissions", value=", ".join(permission_names), inline=False)
                
            if reason:
                embed.add_field(name="Reason", value=reason, inline=False)
                
            embed.add_field(name="Role ID", value=role.id, inline=False)
            embed.set_footer(text=f"Created by {interaction.user.name} • {discord.utils.utcnow().strftime('%d/%m/%Y %H:%M')}")
            
            # Add secondary buttons
            view = discord.ui.View(timeout=60)
            
            # Permissions button
            permissions_button = discord.ui.Button(
                label="Set Permissions", 
                style=discord.ButtonStyle.primary, 
                custom_id=f"permissions_{role.id}"
            )
            
            # Delete button
            delete_button = discord.ui.Button(
                label="Delete Role", 
                style=discord.ButtonStyle.danger, 
                custom_id=f"delete_role_{role.id}"
            )
            
            view.add_item(permissions_button)
            view.add_item(delete_button)
            
            await interaction.followup.send(embed=embed, view=view, ephemeral=False)
            
        except discord.Forbidden:
            await interaction.followup.send("Could not create role: Permission error.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"Could not create role: {str(e)}", ephemeral=True)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if not interaction.data or not interaction.data.get('custom_id'):
            return
            
        custom_id = interaction.data['custom_id']
        
        # Auto role button
        if custom_id.startswith('autorole_'):
            role_id = int(custom_id.split('_')[1])
            role = interaction.guild.get_role(role_id)
            
            if not role:
                return await interaction.response.send_message("This role no longer exists.", ephemeral=True)
                
            # Check if the bot has permission to manage roles
            if not interaction.guild.me.guild_permissions.manage_roles:
                return await interaction.response.send_message("Bot has no permission to manage roles.", ephemeral=True)
                
            # Check if the role is higher than the bot's highest role
            if role.position >= interaction.guild.me.top_role.position:
                return await interaction.response.send_message(f"Bot cannot manage a role higher than its own ({role.mention}).", ephemeral=True)
                
            # Check if the user already has this role
            if role in interaction.user.roles:
                # Remove the role
                try:
                    await interaction.user.remove_roles(role)
                    await interaction.response.send_message(f"**{role.name}** role has been removed.", ephemeral=True)
                except discord.Forbidden:
                    await interaction.response.send_message("Permission error: Cannot remove role.", ephemeral=True)
                except discord.HTTPException as e:
                    await interaction.response.send_message(f"An error occurred while removing the role: {str(e)}", ephemeral=True)
            else:
                # Add the role
                try:
                    await interaction.user.add_roles(role)
                    await interaction.response.send_message(f"**{role.name}** role has been added.", ephemeral=True)
                except discord.Forbidden:
                    await interaction.response.send_message("Permission error: Cannot add role.", ephemeral=True)
                except discord.HTTPException as e:
                    await interaction.response.send_message(f"An error occurred while adding the role: {str(e)}", ephemeral=True)
        
        # Permissions button
        elif custom_id.startswith('permissions_'):
            role_id = int(custom_id.split('_')[1])
            role = interaction.guild.get_role(role_id)
            
            if not role:
                return await interaction.response.send_message("This role no longer exists.", ephemeral=True)
                
            # Check permissions
            if not interaction.user.guild_permissions.manage_roles:
                return await interaction.response.send_message("You need 'Manage Roles' permission for this action.", ephemeral=True)
                
            # Create a dictionary of all permissions and their states
            perm_dict = {}
            for perm, value in role.permissions:
                perm_dict[perm] = value
            
            # Create selection menus for permission categories
            await interaction.response.send_message("Setting up role permissions...", ephemeral=True)
            
            # General Permissions
            general_perms = discord.ui.Select(
                placeholder="General Permissions",
                custom_id=f"gen_perms_{role.id}",
                min_values=0,
                max_values=6,
                options=[
                    discord.SelectOption(label="Administrator", value="administrator", default=perm_dict.get("administrator", False)),
                    discord.SelectOption(label="View Audit Log", value="view_audit_log", default=perm_dict.get("view_audit_log", False)),
                    discord.SelectOption(label="Manage Server", value="manage_guild", default=perm_dict.get("manage_guild", False)),
                    discord.SelectOption(label="Manage Roles", value="manage_roles", default=perm_dict.get("manage_roles", False)),
                    discord.SelectOption(label="Manage Channels", value="manage_channels", default=perm_dict.get("manage_channels", False)),
                    discord.SelectOption(label="Kick Members", value="kick_members", default=perm_dict.get("kick_members", False)),
                    discord.SelectOption(label="Ban Members", value="ban_members", default=perm_dict.get("ban_members", False)),
                ]
            )
            
            # Text Channel Permissions
            text_perms = discord.ui.Select(
                placeholder="Text Channel Permissions",
                custom_id=f"text_perms_{role.id}",
                min_values=0,
                max_values=10,
                options=[
                    discord.SelectOption(label="View Channels", value="view_channel", default=perm_dict.get("view_channel", False)),
                    discord.SelectOption(label="Manage Messages", value="manage_messages", default=perm_dict.get("manage_messages", False)),
                    discord.SelectOption(label="Send Messages", value="send_messages", default=perm_dict.get("send_messages", False)),
                    discord.SelectOption(label="Embed Links", value="embed_links", default=perm_dict.get("embed_links", False)),
                    discord.SelectOption(label="Attach Files", value="attach_files", default=perm_dict.get("attach_files", False)),
                    discord.SelectOption(label="Add Reactions", value="add_reactions", default=perm_dict.get("add_reactions", False)),
                    discord.SelectOption(label="Use External Emojis", value="use_external_emojis", default=perm_dict.get("use_external_emojis", False)),
                    discord.SelectOption(label="Mention @everyone", value="mention_everyone", default=perm_dict.get("mention_everyone", False)),
                    discord.SelectOption(label="Manage Webhooks", value="manage_webhooks", default=perm_dict.get("manage_webhooks", False)),
                    discord.SelectOption(label="Read Message History", value="read_message_history", default=perm_dict.get("read_message_history", False)),
                ]
            )
            
            # Voice Channel Permissions
            voice_perms = discord.ui.Select(
                placeholder="Voice Channel Permissions",
                custom_id=f"voice_perms_{role.id}",
                min_values=0,
                max_values=8,
                options=[
                    discord.SelectOption(label="Connect", value="connect", default=perm_dict.get("connect", False)),
                    discord.SelectOption(label="Speak", value="speak", default=perm_dict.get("speak", False)),
                    discord.SelectOption(label="Stream", value="stream", default=perm_dict.get("stream", False)),
                    discord.SelectOption(label="Mute Members", value="mute_members", default=perm_dict.get("mute_members", False)),
                    discord.SelectOption(label="Deafen Members", value="deafen_members", default=perm_dict.get("deafen_members", False)),
                    discord.SelectOption(label="Move Members", value="move_members", default=perm_dict.get("move_members", False)),
                    discord.SelectOption(label="Use Voice Activity", value="use_voice_activation", default=perm_dict.get("use_voice_activation", False)),
                    discord.SelectOption(label="Priority Speaker", value="priority_speaker", default=perm_dict.get("priority_speaker", False)),
                ]
            )
            
            # Save button
            save_button = discord.ui.Button(
                label="Save Permissions", 
                style=discord.ButtonStyle.success, 
                custom_id=f"save_perms_{role.id}"
            )
            
            # Create view
            view = discord.ui.View(timeout=300)
            view.add_item(general_perms)
            view.add_item(text_perms)
            view.add_item(voice_perms)
            view.add_item(save_button)
            
            await interaction.edit_original_response(content="Select the permissions you want to grant to this role:", view=view)
        
        # Save permissions button
        elif custom_id.startswith('save_perms_'):
            role_id = int(custom_id.split('_')[2])
            role = interaction.guild.get_role(role_id)
            
            if not role:
                return await interaction.response.send_message("This role no longer exists.", ephemeral=True)
            
            # Get all selected values from the interaction
            selected_perms = []
            for component in interaction.data.get('components', []):
                for child in component.get('components', []):
                    if 'values' in child:
                        selected_perms.extend(child.get('values', []))
            
            # Create permissions object
            permissions = discord.Permissions.none()
            for perm in selected_perms:
                setattr(permissions, perm, True)
            
            # Update role permissions
            try:
                await role.edit(permissions=permissions, reason=f"Permissions updated by {interaction.user}")
                
                # Create an embed showing the updated permissions
                embed = discord.Embed(
                    title="Role Permissions Updated",
                    description=f"Permissions for **{role.name}** have been updated.",
                    color=role.color
                )
                
                if selected_perms:
                    embed.add_field(name="Granted Permissions", value=", ".join(selected_perms), inline=False)
                else:
                    embed.add_field(name="Permissions", value="No permissions were granted.", inline=False)
                    
                embed.set_footer(text=f"Updated by {interaction.user.name} • {discord.utils.utcnow().strftime('%d/%m/%Y %H:%M')}")
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
                
            except discord.Forbidden:
                await interaction.response.send_message("Could not update role permissions: Permission error.", ephemeral=True)
            except discord.HTTPException as e:
                await interaction.response.send_message(f"Could not update role permissions: {str(e)}", ephemeral=True)
        
        # Delete role button
        elif custom_id.startswith('delete_role_'):
            role_id = int(custom_id.split('_')[2])
            role = interaction.guild.get_role(role_id)
            
            if not role:
                return await interaction.response.send_message("This role has already been deleted.", ephemeral=True)
                
            # Permission check
            if not interaction.user.guild_permissions.manage_roles:
                return await interaction.response.send_message("You need 'Manage Roles' permission for this action.", ephemeral=True)
                
            try:
                await role.delete(reason=f"Deleted by {interaction.user.name}")
                await interaction.response.send_message(f"**{role.name}** role has been deleted successfully.", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message("Could not delete role: Permission error.", ephemeral=True)
            except discord.HTTPException as e:
                await interaction.response.send_message(f"Could not delete role: {str(e)}", ephemeral=True)
        
        # Unlock channel button
        elif custom_id.startswith('unlock_'):
            channel_id = int(custom_id.split('_')[1])
            channel = interaction.guild.get_channel(channel_id)
            
            if not channel:
                return await interaction.response.send_message("This channel no longer exists.", ephemeral=True)
            
            # Permission check
            if not interaction.user.guild_permissions.manage_channels:
                return await interaction.response.send_message("You need 'Manage Channels' permission for this action.", ephemeral=True)
            
            try:
                # Get the default role (@everyone)
                default_role = interaction.guild.default_role
                
                # Current overwrites
                overwrites = channel.overwrites_for(default_role)
                
                # Set send_messages permission to None (reset to default)
                overwrites.update(send_messages=None)
                
                # If the resulting overwrite is empty, remove it entirely
                if overwrites.is_empty():
                    await channel.set_permissions(
                        default_role, 
                        overwrite=None,
                        reason=f"Channel unlocked by {interaction.user.name} using button"
                    )
                else:
                    await channel.set_permissions(
                        default_role, 
                        overwrite=overwrites,
                        reason=f"Channel unlocked by {interaction.user.name} using button"
                    )
                
                # Create an embed notification
                embed = discord.Embed(
                    title="🔓 Channel Unlocked",
                    description=f"{channel.mention} has been unlocked. Regular members can now send messages again.",
                    color=discord.Color.green()
                )
                
                embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
                embed.add_field(name="Date", value=f"<t:{int(discord.utils.utcnow().timestamp())}:F>", inline=False)
                
                await interaction.response.send_message(embed=embed, ephemeral=False)
                
                # Disable the original button
                try:
                    original_message = interaction.message
                    if original_message:
                        # Create a new view with disabled button
                        view = discord.ui.View(timeout=None)
                        disabled_button = discord.ui.Button(
                            label="Channel Unlocked", 
                            style=discord.ButtonStyle.gray, 
                            custom_id=f"unlocked_{channel.id}",
                            disabled=True
                        )
                        view.add_item(disabled_button)
                        
                        await original_message.edit(view=view)
                except:
                    pass
                
                # Send notification in the channel
                channel_embed = discord.Embed(
                    title="🔓 Channel Unlocked",
                    description="This channel has been unlocked. Regular members can now send messages again.",
                    color=discord.Color.green()
                )
                channel_embed.set_footer(text=f"Unlocked by {interaction.user.name}")
                
                await channel.send(embed=channel_embed)
                
            except discord.Forbidden:
                await interaction.response.send_message("Could not unlock channel: Permission error.", ephemeral=True)
            except discord.HTTPException as e:
                await interaction.response.send_message(f"Could not unlock channel: {e}", ephemeral=True)

        # Banlist button
        elif custom_id.startswith('banlist_'):
            parts = custom_id.split('_')
            action = parts[1]
            user_id = int(parts[2])
            
            # Check if the user who clicked is the one who used the command
            if interaction.user.id != user_id:
                return await interaction.response.send_message("You can't use these buttons on someone else's command.", ephemeral=True)
            
            # Get target page based on action
            target_page = 1
            current_page = int(parts[3]) if len(parts) > 3 else 1
            max_pages = int(parts[4]) if len(parts) > 4 else 1
            
            if action == "first":
                target_page = 1
            elif action == "prev":
                target_page = max(1, current_page - 1)
            elif action == "next":
                target_page = min(max_pages, current_page + 1)
            elif action == "last":
                target_page = max_pages
            else:
                return
            
            # Execute ban list command with new page
            await interaction.response.defer(ephemeral=False)
            
            # Check if we have a search parameter
            search = None
            if interaction.message.embeds:
                content = interaction.message.content or ""
                if "search:" in content.lower():
                    # Extract search parameter
                    search_parts = content.split("search:")
                    if len(search_parts) > 1:
                        search = search_parts[1].strip()
            
            # Use the banlist command with the new page
            ctx = await self.bot.get_context(interaction.message)
            banlist_command = self.bot.get_command("banlist")
            
            if banlist_command:
                await ctx.invoke(banlist_command, page=target_page, search=search)
            else:
                # Manually update the ban list
                try:
                    # Fetch all bans from the server
                    ban_entries = [entry async for entry in interaction.guild.bans()]
                    
                    # If there are no bans
                    if not ban_entries:
                        return await interaction.followup.send("There are no banned users on this server.")
                    
                    # Filter bans if search parameter is provided
                    if search:
                        search = search.lower()
                        filtered_bans = []
                        
                        for ban in ban_entries:
                            # Search in username, display name, and reason
                            username = ban.user.name.lower()
                            reason = ban.reason.lower() if ban.reason else ""
                            
                            if search in username or search in reason:
                                filtered_bans.append(ban)
                        
                        ban_entries = filtered_bans
                        
                        # If no bans match the search
                        if not ban_entries:
                            return await interaction.followup.send(f"No banned users found matching search: `{search}`")
                    
                    # Paginate results (10 bans per page)
                    items_per_page = 10
                    pages = math.ceil(len(ban_entries) / items_per_page)
                    
                    # Validate page number
                    if target_page < 1:
                        target_page = 1
                    elif target_page > pages:
                        target_page = pages
                    
                    # Calculate start and end indices for the current page
                    start = (target_page - 1) * items_per_page
                    end = min(start + items_per_page, len(ban_entries))
                    
                    # Create embed
                    embed = discord.Embed(
                        title=f"Ban List - {interaction.guild.name}",
                        description=f"Showing {start+1}-{end} of {len(ban_entries)} ban{'s' if len(ban_entries) != 1 else ''}",
                        color=discord.Color.red()
                    )
                    
                    # Add banned users to the embed
                    for i, ban in enumerate(ban_entries[start:end], start=start+1):
                        user = ban.user
                        reason = ban.reason or "No reason provided"
                        
                        # Truncate long reasons
                        if len(reason) > 100:
                            reason = reason[:97] + "..."
                        
                        # Format ban entry
                        value = f"**ID:** {user.id}\n**Reason:** {reason}"
                        embed.add_field(
                            name=f"{i}. {user.name}#{user.discriminator if user.discriminator != '0' else ''}",
                            value=value,
                            inline=False
                        )
                    
                    # Add pagination info to footer
                    embed.set_footer(text=f"Page {target_page}/{pages} • Use /banlist [page] to view more")
                    
                    # Create navigation buttons if there are multiple pages
                    view = None
                    if pages > 1:
                        view = discord.ui.View(timeout=120)
                        
                        # First page button
                        first_button = discord.ui.Button(
                            label="<<", 
                            style=discord.ButtonStyle.gray,
                            custom_id=f"banlist_first_{interaction.user.id}",
                            disabled=(target_page == 1)
                        )
                        
                        # Previous page button
                        prev_button = discord.ui.Button(
                            label="<", 
                            style=discord.ButtonStyle.blurple,
                            custom_id=f"banlist_prev_{interaction.user.id}_{target_page}",
                            disabled=(target_page == 1)
                        )
                        
                        # Current page indicator
                        page_button = discord.ui.Button(
                            label=f"{target_page}/{pages}", 
                            style=discord.ButtonStyle.gray,
                            custom_id=f"banlist_page",
                            disabled=True
                        )
                        
                        # Next page button
                        next_button = discord.ui.Button(
                            label=">", 
                            style=discord.ButtonStyle.blurple,
                            custom_id=f"banlist_next_{interaction.user.id}_{target_page}",
                            disabled=(target_page == pages)
                        )
                        
                        # Last page button
                        last_button = discord.ui.Button(
                            label=">>", 
                            style=discord.ButtonStyle.gray,
                            custom_id=f"banlist_last_{interaction.user.id}_{pages}",
                            disabled=(target_page == pages)
                        )
                        
                        view.add_item(first_button)
                        view.add_item(prev_button)
                        view.add_item(page_button)
                        view.add_item(next_button)
                        view.add_item(last_button)
                    
                    await interaction.message.edit(embed=embed, view=view)
                    
                except discord.Forbidden:
                    await interaction.followup.send("I don't have permission to view the ban list.", ephemeral=True)
                except discord.HTTPException as e:
                    await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)
                except Exception as e:
                    await interaction.followup.send(f"An unexpected error occurred: {e}", ephemeral=True)

    @app_commands.command(name="ban", description="Ban a user from the server")
    @app_commands.default_permissions(ban_members=True)
    @app_commands.guild_only()
    async def ban(self, interaction: discord.Interaction, user: discord.Member, reason: str = None, delete_messages: int = 0):
        # Check if the bot has permission to ban members
        if not interaction.guild.me.guild_permissions.ban_members:
            return await interaction.response.send_message("Bot has no permission to ban members.", ephemeral=True)
        
        # User can't ban themselves
        if user.id == interaction.user.id:
            return await interaction.response.send_message("You cannot ban yourself!", ephemeral=True)
        
        # User can't ban the bot
        if user.id == self.bot.user.id:
            return await interaction.response.send_message("You cannot ban me!", ephemeral=True)
        
        # Check if the user to be banned has higher authority
        if user.top_role.position >= interaction.user.top_role.position and interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message("You cannot ban someone with higher authority than you.", ephemeral=True)
        
        # Check if the user to be banned has higher authority than the bot
        if user.top_role.position >= interaction.guild.me.top_role.position:
            return await interaction.response.send_message("I cannot ban someone with higher authority than me.", ephemeral=True)
        
        await interaction.response.defer(ephemeral=True)
        
        # Ban process
        try:
            # Try to send a DM to the user
            try:
                embed = discord.Embed(
                    title="You Have Been Banned",
                    description=f"You have been banned from **{interaction.guild.name}**.",
                    color=discord.Color.red()
                )
                if reason:
                    embed.add_field(name="Reason", value=reason, inline=False)
                
                await user.send(embed=embed)
            except:
                # Continue if DM can't be sent
                pass
            
            # Ban the user
            await interaction.guild.ban(
                user, 
                reason=f"{interaction.user}: {reason}" if reason else f"Banned by {interaction.user}",
                delete_message_days=delete_messages if delete_messages in [0, 1, 2, 3, 4, 5, 6, 7] else 0
            )
            
            # Create an embed with ban information
            embed = discord.Embed(
                title="User Banned",
                description=f"**{user}** has been banned from the server.",
                color=discord.Color.red()
            )
            embed.add_field(name="ID", value=user.id, inline=True)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            if reason:
                embed.add_field(name="Reason", value=reason, inline=False)
            
            embed.add_field(name="Date", value=f"<t:{int(discord.utils.utcnow().timestamp())}:F>", inline=False)
            
            # Add user avatar to the embed
            if user.avatar:
                embed.set_thumbnail(url=user.avatar.url)
            
            await interaction.followup.send(embed=embed)
            
        except discord.Forbidden:
            await interaction.followup.send("Could not ban user: Permission error.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"Could not ban user: {e}", ephemeral=True)

    @app_commands.command(name="unban", description="Unban a user from the server")
    @app_commands.default_permissions(ban_members=True)
    @app_commands.guild_only()
    async def unban(self, interaction: discord.Interaction, user_id: str, reason: str = None):
        # Check if the bot has permission to unban members
        if not interaction.guild.me.guild_permissions.ban_members:
            return await interaction.response.send_message("Bot has no permission to manage bans.", ephemeral=True)
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Validate user ID
            try:
                user_id = int(user_id)
            except ValueError:
                return await interaction.followup.send("Please enter a valid user ID.", ephemeral=True)
            
            # Get the ban list from the server
            bans = [ban async for ban in interaction.guild.bans()]
            banned_user = discord.utils.find(lambda ban: ban.user.id == user_id, bans)
            
            if not banned_user:
                return await interaction.followup.send("This user is not banned.", ephemeral=True)
            
            # Create an invite to the guild (7 days validity, 1 use)
            invite_link = None
            try:
                # Find a suitable channel for invite creation
                invite_channel = None
                
                # Try to find a "welcome" channel first
                welcome_channels = ["welcome", "lobby", "entrance", "join", "general"]
                for name in welcome_channels:
                    channel = discord.utils.find(
                        lambda c: name in c.name.lower() and isinstance(c, discord.TextChannel), 
                        interaction.guild.channels
                    )
                    if channel and channel.permissions_for(interaction.guild.me).create_instant_invite:
                        invite_channel = channel
                        break
                
                # If no welcome channel found, try any text channel
                if not invite_channel:
                    invite_channel = discord.utils.find(
                        lambda c: isinstance(c, discord.TextChannel) and c.permissions_for(interaction.guild.me).create_instant_invite,
                        interaction.guild.channels
                    )
                
                # Create the invite if a suitable channel was found
                if invite_channel:
                    invite = await invite_channel.create_invite(
                        max_age=604800,  # 7 days
                        max_uses=1,      # 1 use
                        reason=f"Invite for manually unbanned user: {banned_user.user}"
                    )
                    invite_link = invite.url
            except Exception as e:
                print(f"Failed to create invite: {e}")
                invite_link = None
            
            # Unban the user
            await interaction.guild.unban(
                banned_user.user, 
                reason=f"{interaction.user}: {reason}" if reason else f"Unbanned by {interaction.user}"
            )
            
            # Try to send a DM to the user about the unban
            dm_sent = False
            try:
                user = banned_user.user
                
                embed = discord.Embed(
                    title="Your Ban Has Been Lifted",
                    description=f"You have been unbanned from **{interaction.guild.name}**.",
                    color=discord.Color.green()
                )
                
                if invite_link:
                    embed.add_field(name="Invitation", value=f"[Click here to rejoin]({invite_link})\n*This invite link expires in 7 days and can only be used once.*", inline=False)
                else:
                    embed.add_field(name="Note", value="No invite link could be generated. Please contact a server member for a new invite.", inline=False)
                
                if reason:
                    embed.add_field(name="Reason", value=reason, inline=False)
                    
                embed.add_field(name="Unbanned By", value=interaction.user.mention, inline=True)
                embed.add_field(name="Unban Time", value=f"<t:{int(discord.utils.utcnow().timestamp())}:F>", inline=True)
                
                if interaction.guild.icon:
                    embed.set_thumbnail(url=interaction.guild.icon.url)
                    
                embed.set_footer(text=f"Server: {interaction.guild.name}", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
                
                await user.send(embed=embed)
                dm_sent = True
            except:
                # DM might fail if the user has DMs closed or has blocked the bot
                dm_sent = False
            
            # Create an embed with unban information for the server
            embed = discord.Embed(
                title="User Unbanned",
                description=f"**{banned_user.user}** has been unbanned.",
                color=discord.Color.green()
            )
            embed.add_field(name="ID", value=banned_user.user.id, inline=True)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            
            if invite_link:
                embed.add_field(name="Invite Link", value=f"A single-use invite has been created" + (" and sent to the user." if dm_sent else "."), inline=False)
            
            if reason:
                embed.add_field(name="Reason", value=reason, inline=False)
            
            embed.add_field(name="Date", value=f"<t:{int(discord.utils.utcnow().timestamp())}:F>", inline=False)
            
            if not dm_sent:
                embed.add_field(name="Note", value="Could not send DM to the user. They may have DMs disabled.", inline=False)
            
            if banned_user.user.avatar:
                embed.set_thumbnail(url=banned_user.user.avatar.url)
            
            await interaction.followup.send(embed=embed)
            
        except discord.Forbidden:
            await interaction.followup.send("Could not unban user: Permission error.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"Could not unban user: {e}", ephemeral=True)

    @app_commands.command(name="lock", description="Lock a channel to prevent members from sending messages")
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.guild_only()
    async def lock(
        self, 
        interaction: discord.Interaction, 
        channel: discord.TextChannel = None, 
        reason: str = None
    ):
        # Use current channel if not specified
        channel = channel or interaction.channel
        
        # Check if the bot has permission to manage channels
        if not interaction.guild.me.guild_permissions.manage_channels:
            return await interaction.response.send_message("Bot has no permission to manage channels.", ephemeral=True)
        
        # Check if user has permission to manage channels
        if not interaction.user.guild_permissions.manage_channels:
            return await interaction.response.send_message("You need 'Manage Channels' permission to use this command.", ephemeral=True)
        
        await interaction.response.defer(ephemeral=False)
        
        try:
            # Get the default role (@everyone)
            default_role = interaction.guild.default_role
            
            # Save the current permissions for restoration later
            current_perms = channel.overwrites_for(default_role)
            
            # Set send_messages permission to False
            overwrite = discord.PermissionOverwrite(send_messages=False)
            
            # Update the channel permissions
            await channel.set_permissions(
                default_role, 
                overwrite=overwrite,
                reason=f"Channel locked by {interaction.user.name}: {reason}" if reason else f"Channel locked by {interaction.user.name}"
            )
            
            # Create an embed notification
            embed = discord.Embed(
                title="🔒 Channel Locked",
                description=f"This channel has been locked. Regular members can no longer send messages.",
                color=discord.Color.red()
            )
            
            embed.add_field(name="Channel", value=channel.mention, inline=True)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            embed.add_field(name="Date", value=f"<t:{int(discord.utils.utcnow().timestamp())}:F>", inline=False)
            
            if reason:
                embed.add_field(name="Reason", value=reason, inline=False)
            
            # Add button to unlock
            view = discord.ui.View(timeout=None)
            unlock_button = discord.ui.Button(
                label="Unlock Channel", 
                style=discord.ButtonStyle.success, 
                custom_id=f"unlock_{channel.id}"
            )
            view.add_item(unlock_button)
            
            await interaction.followup.send(embed=embed, view=view)
            
            # Send notification in the channel if it's not the same as the interaction channel
            if channel.id != interaction.channel.id:
                channel_embed = discord.Embed(
                    title="🔒 Channel Locked",
                    description="This channel has been locked. Regular members can no longer send messages.",
                    color=discord.Color.red()
                )
                if reason:
                    channel_embed.add_field(name="Reason", value=reason, inline=False)
                channel_embed.set_footer(text=f"Locked by {interaction.user.name}")
                
                await channel.send(embed=channel_embed)
                
        except discord.Forbidden:
            await interaction.followup.send("Could not lock channel: Permission error.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"Could not lock channel: {e}", ephemeral=True)

    @app_commands.command(name="unlock", description="Unlock a previously locked channel")
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.guild_only()
    async def unlock(
        self, 
        interaction: discord.Interaction, 
        channel: discord.TextChannel = None, 
        reason: str = None
    ):
        # Use current channel if not specified
        channel = channel or interaction.channel
        
        # Check if the bot has permission to manage channels
        if not interaction.guild.me.guild_permissions.manage_channels:
            return await interaction.response.send_message("Bot has no permission to manage channels.", ephemeral=True)
        
        # Check if user has permission to manage channels
        if not interaction.user.guild_permissions.manage_channels:
            return await interaction.response.send_message("You need 'Manage Channels' permission to use this command.", ephemeral=True)
        
        await interaction.response.defer(ephemeral=False)
        
        try:
            # Get the default role (@everyone)
            default_role = interaction.guild.default_role
            
            # Current overwrites
            overwrites = channel.overwrites_for(default_role)
            
            # Set send_messages permission to None (reset to default)
            overwrites.update(send_messages=None)
            
            # If the resulting overwrite is empty, remove it entirely
            if overwrites.is_empty():
                await channel.set_permissions(
                    default_role, 
                    overwrite=None,
                    reason=f"Channel unlocked by {interaction.user.name}: {reason}" if reason else f"Channel unlocked by {interaction.user.name}"
                )
            else:
                await channel.set_permissions(
                    default_role, 
                    overwrite=overwrites,
                    reason=f"Channel unlocked by {interaction.user.name}: {reason}" if reason else f"Channel unlocked by {interaction.user.name}"
                )
            
            # Create an embed notification
            embed = discord.Embed(
                title="🔓 Channel Unlocked",
                description=f"This channel has been unlocked. Regular members can now send messages again.",
                color=discord.Color.green()
            )
            
            embed.add_field(name="Channel", value=channel.mention, inline=True)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            embed.add_field(name="Date", value=f"<t:{int(discord.utils.utcnow().timestamp())}:F>", inline=False)
            
            if reason:
                embed.add_field(name="Reason", value=reason, inline=False)
            
            await interaction.followup.send(embed=embed)
            
            # Send notification in the channel if it's not the same as the interaction channel
            if channel.id != interaction.channel.id:
                channel_embed = discord.Embed(
                    title="🔓 Channel Unlocked",
                    description="This channel has been unlocked. Regular members can now send messages again.",
                    color=discord.Color.green()
                )
                if reason:
                    channel_embed.add_field(name="Reason", value=reason, inline=False)
                channel_embed.set_footer(text=f"Unlocked by {interaction.user.name}")
                
                await channel.send(embed=channel_embed)
                
        except discord.Forbidden:
            await interaction.followup.send("Could not unlock channel: Permission error.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"Could not unlock channel: {e}", ephemeral=True)

    @app_commands.command(name="tempban", description="Temporarily ban a user for a specified duration")
    @app_commands.default_permissions(ban_members=True)
    @app_commands.guild_only()
    async def tempban(
        self, 
        interaction: discord.Interaction, 
        user: discord.Member, 
        duration: str,
        reason: str = None,
        delete_messages: int = 0
    ):
        """
        Temporarily ban a user for a specified duration
        
        Parameters
        -----------
        user: The user to ban
        duration: Ban duration (e.g. 1d, 12h, 30m, 1d12h30m)
        reason: Reason for the ban
        delete_messages: Number of days worth of messages to delete (0-7)
        """
        # Check if the bot has permission to ban members
        if not interaction.guild.me.guild_permissions.ban_members:
            return await interaction.response.send_message("Bot has no permission to ban members.", ephemeral=True)
        
        # User can't ban themselves
        if user.id == interaction.user.id:
            return await interaction.response.send_message("You cannot ban yourself!", ephemeral=True)
        
        # User can't ban the bot
        if user.id == self.bot.user.id:
            return await interaction.response.send_message("You cannot ban me!", ephemeral=True)
        
        # Check if the user to be banned has higher authority
        if user.top_role.position >= interaction.user.top_role.position and interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message("You cannot ban someone with higher authority than you.", ephemeral=True)
        
        # Check if the user to be banned has higher authority than the bot
        if user.top_role.position >= interaction.guild.me.top_role.position:
            return await interaction.response.send_message("I cannot ban someone with higher authority than me.", ephemeral=True)
        
        # Parse duration
        seconds = 0
        pattern = re.compile(r'(\d+)([smhdw])')
        matches = pattern.findall(duration.lower())
        
        if not matches:
            return await interaction.response.send_message(
                "Invalid duration format. Examples: `30m`, `1h`, `1d`, `1w`, `1d12h30m`", 
                ephemeral=True
            )
        
        time_mapping = {
            's': 1,             # seconds
            'm': 60,            # minutes
            'h': 3600,          # hours
            'd': 86400,         # days
            'w': 604800         # weeks
        }
        
        for value, unit in matches:
            seconds += int(value) * time_mapping[unit]
        
        if seconds < 60:
            return await interaction.response.send_message("Duration must be at least 1 minute.", ephemeral=True)
        
        if seconds > 2592000:  # 30 days
            return await interaction.response.send_message("Duration cannot exceed 30 days.", ephemeral=True)
        
        # Format the duration for display
        duration_delta = datetime.timedelta(seconds=seconds)
        formatted_duration = self.format_timedelta(duration_delta)
        unban_time = discord.utils.utcnow() + duration_delta
        
        await interaction.response.defer(ephemeral=False)
        
        # Store user info for later use when unbanning
        user_info = {
            "id": user.id,
            "name": user.name,
            "avatar_url": user.avatar.url if user.avatar else None,
            "discriminator": user.discriminator
        }
        
        # Ban process
        try:
            # Try to send a DM to the user
            try:
                embed = discord.Embed(
                    title="You Have Been Temporarily Banned",
                    description=f"You have been banned from **{interaction.guild.name}** for {formatted_duration}.",
                    color=discord.Color.red()
                )
                if reason:
                    embed.add_field(name="Reason", value=reason, inline=False)
                
                embed.add_field(name="Ban Expires", value=f"<t:{int(unban_time.timestamp())}:F>", inline=False)
                embed.add_field(name="Note", value="You will receive a DM with an invite link when your ban expires.", inline=False)
                
                if interaction.guild.icon:
                    embed.set_thumbnail(url=interaction.guild.icon.url)
                    
                embed.set_footer(text=f"Server: {interaction.guild.name}", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
                
                await user.send(embed=embed)
            except:
                # Continue if DM can't be sent
                pass
            
            # Ban the user
            await interaction.guild.ban(
                user, 
                reason=f"Temp banned by {interaction.user} for {formatted_duration}: {reason}" if reason else f"Temp banned by {interaction.user} for {formatted_duration}",
                delete_message_days=delete_messages if delete_messages in [0, 1, 2, 3, 4, 5, 6, 7] else 0
            )
            
            # Create an embed with ban information
            embed = discord.Embed(
                title="User Temporarily Banned",
                description=f"**{user}** has been banned from the server for {formatted_duration}.",
                color=discord.Color.red()
            )
            embed.add_field(name="User ID", value=user.id, inline=True)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            if reason:
                embed.add_field(name="Reason", value=reason, inline=False)
            
            embed.add_field(name="Duration", value=formatted_duration, inline=True)
            embed.add_field(name="Ban Expires", value=f"<t:{int(unban_time.timestamp())}:F>", inline=True)
            
            # Add user avatar to the embed
            if user.avatar:
                embed.set_thumbnail(url=user.avatar.url)
            
            # Schedule the unban task
            self.bot.loop.create_task(self.schedule_unban(
                guild=interaction.guild,
                user_id=user.id,
                user_info=user_info,
                unban_time=unban_time,
                moderator=interaction.user,
                reason=reason
            ))
            
            await interaction.followup.send(embed=embed)
            
        except discord.Forbidden:
            await interaction.followup.send("Could not ban user: Permission error.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"Could not ban user: {e}", ephemeral=True)

    # Helper method for formatting time delta
    def format_timedelta(self, delta):
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        parts = []
        if days:
            parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes:
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        if seconds and not days and not hours:
            parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
        
        return " ".join(parts)

    # Method to handle scheduled unbans
    async def schedule_unban(self, guild, user_id, user_info, unban_time, moderator, reason=None):
        # Calculate sleep time
        now = discord.utils.utcnow()
        sleep_seconds = (unban_time - now).total_seconds()
        
        # Ensure positive sleep time
        if sleep_seconds <= 0:
            return
        
        # Sleep until unban time
        await asyncio.sleep(sleep_seconds)
        
        try:
            # Check if the user is still banned
            bans = [ban async for ban in guild.bans()]
            banned_user = discord.utils.find(lambda ban: ban.user.id == user_id, bans)
            
            if banned_user:
                # Create an invite to the guild (7 days validity, 1 use)
                try:
                    # Find a suitable channel for invite creation
                    invite_channel = None
                    
                    # Try to find a "welcome" channel first
                    welcome_channels = ["welcome", "lobby", "entrance", "join", "general"]
                    for name in welcome_channels:
                        channel = discord.utils.find(
                            lambda c: name in c.name.lower() and isinstance(c, discord.TextChannel), 
                            guild.channels
                        )
                        if channel and channel.permissions_for(guild.me).create_instant_invite:
                            invite_channel = channel
                            break
                    
                    # If no welcome channel found, try any text channel
                    if not invite_channel:
                        invite_channel = discord.utils.find(
                            lambda c: isinstance(c, discord.TextChannel) and c.permissions_for(guild.me).create_instant_invite,
                            guild.channels
                        )
                    
                    # Create the invite if a suitable channel was found
                    invite_link = None
                    if invite_channel:
                        invite = await invite_channel.create_invite(
                            max_age=604800,  # 7 days
                            max_uses=1,      # 1 use
                            reason=f"Auto-generated invite for unbanned user: {banned_user.user}"
                        )
                        invite_link = invite.url
                except Exception as e:
                    print(f"Failed to create invite: {e}")
                    invite_link = None
                
                # Unban the user
                await guild.unban(
                    banned_user.user, 
                    reason=f"Temporary ban expired. Originally banned by {moderator}"
                )
                
                # Try to send a DM to the user about the unban
                try:
                    user = banned_user.user
                    
                    embed = discord.Embed(
                        title="Your Ban Has Been Lifted",
                        description=f"Your temporary ban from **{guild.name}** has expired. You can now rejoin the server.",
                        color=discord.Color.green()
                    )
                    
                    if invite_link:
                        embed.add_field(name="Invitation", value=f"[Click here to rejoin]({invite_link})\n*This invite link expires in 7 days and can only be used once.*", inline=False)
                    else:
                        embed.add_field(name="Note", value="No invite link could be generated. Please contact a server member for a new invite.", inline=False)
                    
                    embed.add_field(name="Original Ban Reason", value=reason or "No reason specified", inline=False)
                    embed.add_field(name="Unban Time", value=f"<t:{int(discord.utils.utcnow().timestamp())}:F>", inline=False)
                    
                    if guild.icon:
                        embed.set_thumbnail(url=guild.icon.url)
                        
                    embed.set_footer(text=f"Server: {guild.name}", icon_url=guild.icon.url if guild.icon else None)
                    
                    # Try to fetch the user if not found
                    if not user:
                        user = await self.bot.fetch_user(user_id)
                    
                    await user.send(embed=embed)
                except:
                    # DM might fail if the user has DMs closed or has blocked the bot
                    pass
                
                # Try to find a log channel to notify the server
                log_channel = discord.utils.find(
                    lambda c: any(keyword in c.name.lower() for keyword in ['mod', 'log', 'admin', 'ban']) and 
                              isinstance(c, discord.TextChannel) and 
                              c.permissions_for(guild.me).send_messages, 
                    guild.channels
                )
                
                if log_channel:
                    log_embed = discord.Embed(
                        title="Temporary Ban Expired",
                        description=f"**{banned_user.user}** has been unbanned automatically.",
                        color=discord.Color.green()
                    )
                    log_embed.add_field(name="User ID", value=user_id, inline=True)
                    log_embed.add_field(name="Original Moderator", value=moderator.mention, inline=True)
                    
                    if invite_link:
                        log_embed.add_field(name="Invite Sent", value=f"A single-use invite link was sent to the user.", inline=False)
                    
                    if reason:
                        log_embed.add_field(name="Original Reason", value=reason, inline=False)
                        
                    log_embed.add_field(name="Unban Time", value=f"<t:{int(discord.utils.utcnow().timestamp())}:F>", inline=False)
                    
                    if banned_user.user.avatar:
                        log_embed.set_thumbnail(url=banned_user.user.avatar.url)
                    
                    await log_channel.send(embed=log_embed)
                    
        except (discord.Forbidden, discord.HTTPException, discord.NotFound) as e:
            # Log the error to console
            print(f"Error in unban process: {e}")

    @app_commands.command(name="banlist", description="Show the list of banned users on this server")
    @app_commands.default_permissions(ban_members=True)
    @app_commands.guild_only()
    async def banlist(
        self, 
        interaction: discord.Interaction, 
        page: int = 1,
        search: str = None
    ):
        """
        Show the list of banned users on this server
        
        Parameters
        -----------
        page: Page number to view (default: 1)
        search: Filter bans by username or reason (optional)
        """
        # Check if the bot has permission to view bans
        if not interaction.guild.me.guild_permissions.ban_members:
            return await interaction.response.send_message("Bot has no permission to view ban list.", ephemeral=True)
        
        # Check if the user has permission to view bans
        if not interaction.user.guild_permissions.ban_members:
            return await interaction.response.send_message("You need 'Ban Members' permission to use this command.", ephemeral=True)
        
        await interaction.response.defer(ephemeral=False)
        
        try:
            # Fetch all bans from the server
            ban_entries = [entry async for entry in interaction.guild.bans()]
            
            # If there are no bans
            if not ban_entries:
                return await interaction.followup.send("There are no banned users on this server.")
            
            # Filter bans if search parameter is provided
            if search:
                search = search.lower()
                filtered_bans = []
                
                for ban in ban_entries:
                    # Search in username, display name, and reason
                    username = ban.user.name.lower()
                    reason = ban.reason.lower() if ban.reason else ""
                    
                    if search in username or search in reason:
                        filtered_bans.append(ban)
                
                ban_entries = filtered_bans
                
                # If no bans match the search
                if not ban_entries:
                    return await interaction.followup.send(f"No banned users found matching search: `{search}`")
            
            # Paginate results (10 bans per page)
            items_per_page = 10
            pages = math.ceil(len(ban_entries) / items_per_page)
            
            # Validate page number
            if page < 1:
                page = 1
            elif page > pages:
                page = pages
            
            # Calculate start and end indices for the current page
            start = (page - 1) * items_per_page
            end = min(start + items_per_page, len(ban_entries))
            
            # Create embed
            embed = discord.Embed(
                title=f"Ban List - {interaction.guild.name}",
                description=f"Showing {start+1}-{end} of {len(ban_entries)} ban{'s' if len(ban_entries) != 1 else ''}",
                color=discord.Color.red()
            )
            
            # Add banned users to the embed
            for i, ban in enumerate(ban_entries[start:end], start=start+1):
                user = ban.user
                reason = ban.reason or "No reason provided"
                
                # Truncate long reasons
                if len(reason) > 100:
                    reason = reason[:97] + "..."
                
                # Format ban entry
                value = f"**ID:** {user.id}\n**Reason:** {reason}"
                embed.add_field(
                    name=f"{i}. {user.name}#{user.discriminator if user.discriminator != '0' else ''}",
                    value=value,
                    inline=False
                )
            
            # Add pagination info to footer
            embed.set_footer(text=f"Page {page}/{pages} • Use /banlist [page] to view more")
            
            # Create navigation buttons if there are multiple pages
            view = None
            if pages > 1:
                view = discord.ui.View(timeout=120)
                
                # First page button
                first_button = discord.ui.Button(
                    label="<<", 
                    style=discord.ButtonStyle.gray,
                    custom_id=f"banlist_first_{interaction.user.id}",
                    disabled=(page == 1)
                )
                
                # Previous page button
                prev_button = discord.ui.Button(
                    label="<", 
                    style=discord.ButtonStyle.blurple,
                    custom_id=f"banlist_prev_{interaction.user.id}_{page}",
                    disabled=(page == 1)
                )
                
                # Current page indicator
                page_button = discord.ui.Button(
                    label=f"{page}/{pages}", 
                    style=discord.ButtonStyle.gray,
                    custom_id=f"banlist_page",
                    disabled=True
                )
                
                # Next page button
                next_button = discord.ui.Button(
                    label=">", 
                    style=discord.ButtonStyle.blurple,
                    custom_id=f"banlist_next_{interaction.user.id}_{page}",
                    disabled=(page == pages)
                )
                
                # Last page button
                last_button = discord.ui.Button(
                    label=">>", 
                    style=discord.ButtonStyle.gray,
                    custom_id=f"banlist_last_{interaction.user.id}_{pages}",
                    disabled=(page == pages)
                )
                
                view.add_item(first_button)
                view.add_item(prev_button)
                view.add_item(page_button)
                view.add_item(next_button)
                view.add_item(last_button)
            
            await interaction.followup.send(embed=embed, view=view)
            
        except discord.Forbidden:
            await interaction.followup.send("I don't have permission to view the ban list.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"An unexpected error occurred: {e}", ephemeral=True)

    @app_commands.command(name="autorolemessage", description="Creates an interactive message for automatic role assignment")
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.guild_only()
    async def autorolemessage(
        self, 
        interaction: discord.Interaction, 
        channel: discord.TextChannel, 
        role: discord.Role,
        message: str
    ):
        """
        Creates an interactive message for automatic role assignment
        
        Parameters
        -----------
        channel: The channel to send the message to
        role: The role to assign
        message: Message content
        """
        # Check if the bot has permission to manage roles
        if not interaction.guild.me.guild_permissions.manage_roles:
            return await interaction.response.send_message("Bot has no permission to manage roles.", ephemeral=True)
        
        # Check if the user has permission to manage roles
        if not interaction.user.guild_permissions.manage_roles:
            return await interaction.response.send_message("You must have the 'Manage Roles' permission to use this command.", ephemeral=True)
        
        # Check if the role is higher than the bot's highest role
        if role.position >= interaction.guild.me.top_role.position:
            return await interaction.response.send_message(f"Bot cannot assign a role higher than its own ({role.mention}).", ephemeral=True)
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Create the embed message
            embed = discord.Embed(
                title="Role Assignment",
                description=message,
                color=role.color
            )
            embed.add_field(name="Role", value=f"{role.mention}", inline=True)
            embed.add_field(name="Usage", value="Click the button below to get the role.\nClick again to remove the role.", inline=False)
            embed.set_footer(text=f"Role ID: {role.id}")
            
            # Buton ekle
            view = discord.ui.View(timeout=None)
            button = discord.ui.Button(
                label=f"Toggle {role.name} Role", 
                style=discord.ButtonStyle.primary, 
                custom_id=f"autorole_{role.id}"
            )
            view.add_item(button)
            
            # Mesajı gönder
            role_message = await channel.send(embed=embed, view=view)
            
            # Onay mesajı
            success_embed = discord.Embed(
                title="Auto Role Message Created",
                description=f"Auto role message sent to {channel.mention}.",
                color=discord.Color.green()
            )
            success_embed.add_field(name="Role", value=f"{role.mention}", inline=True)
            success_embed.add_field(name="Message Link", value=f"[Click here]({role_message.jump_url})", inline=True)
            
            await interaction.followup.send(embed=success_embed, ephemeral=True)
            
        except discord.Forbidden:
            await interaction.followup.send("Permission error: Cannot send message or manage roles.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)

    @app_commands.command(name="joinleaveset", description="Set the channel for join/leave messages")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def joinleaveset(
        self, 
        interaction: discord.Interaction, 
        channel: discord.TextChannel
    ):
        """
        Set the channel for join/leave messages
        
        Parameters
        -----------
        channel: The channel to send join/leave messages to
        """
        # Check if the user has permission to manage the guild
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("You must have the 'Manage Server' permission to use this command.", ephemeral=True)
            
        # Check if the bot has permission to send messages in the channel
        if not channel.permissions_for(interaction.guild.me).send_messages:
            return await interaction.response.send_message(f"Bot cannot send messages in {channel.mention}. Please check permissions.", ephemeral=True)
            
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Create configs directory if it doesn't exist
            os.makedirs('configs', exist_ok=True)
            
            # Load existing configs
            config_file = 'configs.json'
            configs = {}
            
            if os.path.exists(config_file):
                try:
                    with open(config_file, 'r') as f:
                        configs = json.load(f)
                except json.JSONDecodeError:
                    # If JSON is invalid, start with empty config
                    configs = {}
            
            # Initialize joinleave section if not exists
            if 'joinleave' not in configs:
                configs['joinleave'] = {}
                
            # Initialize guild section if not exists
            if 'guilds' not in configs['joinleave']:
                configs['joinleave']['guilds'] = {}
                
            # Set channel for this guild
            guild_id = str(interaction.guild.id)
            configs['joinleave']['guilds'][guild_id] = {
                'channel_id': channel.id,
                'channel_name': channel.name
            }
            
            # Save the config
            with open(config_file, 'w') as f:
                json.dump(configs, f, indent=4)
                
            # Confirmation message
            embed = discord.Embed(
                title="Join/Leave Channel Set",
                description=f"Join and leave messages will now be sent to {channel.mention}.",
                color=discord.Color.green()
            )
            embed.add_field(name="Server", value=interaction.guild.name, inline=True)
            embed.add_field(name="Channel", value=channel.mention, inline=True)
            embed.set_footer(text="You can change this setting at any time with /joinleaveset")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)

    @app_commands.command(name="modlogset", description="Set the channel for moderator action logs")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def modlogset(
        self, 
        interaction: discord.Interaction, 
        channel: discord.TextChannel
    ):
        """
        Set the channel for moderator action logs
        
        Parameters
        -----------
        channel: The channel to send moderation logs to
        """
        # Check if the user has administrator permission
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("You must have the 'Administrator' permission to use this command.", ephemeral=True)
            
        # Check if the bot has permission to send messages in the channel
        if not channel.permissions_for(interaction.guild.me).send_messages:
            return await interaction.response.send_message(f"Bot cannot send messages in {channel.mention}. Please check permissions.", ephemeral=True)
            
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Create configs directory if it doesn't exist
            os.makedirs('configs', exist_ok=True)
            
            # Load existing configs
            config_file = 'configs.json'
            configs = {}
            
            if os.path.exists(config_file):
                try:
                    with open(config_file, 'r') as f:
                        configs = json.load(f)
                except json.JSONDecodeError:
                    # If JSON is invalid, start with empty config
                    configs = {}
            
            # Initialize modlog section if not exists
            if 'modlog' not in configs:
                configs['modlog'] = {}
                
            # Initialize guild section if not exists
            if 'guilds' not in configs['modlog']:
                configs['modlog']['guilds'] = {}
                
            # Set channel for this guild
            guild_id = str(interaction.guild.id)
            configs['modlog']['guilds'][guild_id] = {
                'channel_id': channel.id,
                'channel_name': channel.name
            }
            
            # Save the config
            with open(config_file, 'w') as f:
                json.dump(configs, f, indent=4)
                
            # Confirmation message
            embed = discord.Embed(
                title="Moderation Log Channel Set",
                description=f"Moderation action logs will now be sent to {channel.mention}.",
                color=discord.Color.blue()
            )
            embed.add_field(name="Server", value=interaction.guild.name, inline=True)
            embed.add_field(name="Channel", value=channel.mention, inline=True)
            embed.set_footer(text="You can change this setting at any time with /modlogset")
            
            # Log the setup action itself
            log_embed = discord.Embed(
                title="Modlog Configured",
                description=f"Moderation logs were configured to be sent to this channel.",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            log_embed.add_field(name="Administrator", value=f"{interaction.user.mention} ({interaction.user.name})", inline=True)
            log_embed.set_footer(text=f"Server ID: {interaction.guild.id}")
            
            await channel.send(embed=log_embed)
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)

    @commands.Cog.listener()
    async def on_app_command_completion(self, interaction: discord.Interaction, command: app_commands.Command):
        """Event listener for when a slash command is successfully executed"""
        try:
            # Only log if the command was successfully executed
            if interaction.response.is_done():
                # Get guild ID
                if not interaction.guild:
                    return  # Skip DM commands
                    
                guild_id = str(interaction.guild.id)
                
                # Get the configured log channel
                log_channel = await self.get_modlog_channel(interaction.guild)
                if not log_channel:
                    return
                    
                # Create a log embed
                embed = discord.Embed(
                    title="Command Executed",
                    description=f"Slash command `/{command.name}` was executed",
                    color=discord.Color.blue(),
                    timestamp=discord.utils.utcnow()
                )
                
                # Add command info
                embed.add_field(name="User", value=f"{interaction.user.mention} ({interaction.user.name})", inline=True)
                embed.add_field(name="Channel", value=f"{interaction.channel.mention}", inline=True)
                
                # Add command options if any
                if interaction.data.get('options'):
                    options_str = ""
                    for option in interaction.data.get('options', []):
                        if 'value' in option:
                            # Simple option
                            value = option['value']
                            # If the value is a user/role/channel ID, try to get the name
                            if option.get('type') == 6:  # User type
                                user = interaction.guild.get_member(int(value))
                                if user:
                                    value = f"{user.mention} ({user.name})"
                            elif option.get('type') == 8:  # Role type
                                role = interaction.guild.get_role(int(value))
                                if role:
                                    value = f"{role.mention} ({role.name})"
                            elif option.get('type') == 7:  # Channel type
                                channel = interaction.guild.get_channel(int(value))
                                if channel:
                                    value = f"{channel.mention} ({channel.name})"
                            
                            options_str += f"`{option['name']}`: {value}\n"
                        else:
                            # Subcommand or subcommand group
                            options_str += f"Subcommand: `{option['name']}`\n"
                            # Process the subcommand's options
                            for suboption in option.get('options', []):
                                if 'value' in suboption:
                                    options_str += f"`{suboption['name']}`: {suboption['value']}\n"
                    
                    if options_str:
                        embed.add_field(name="Options", value=options_str, inline=False)
                
                # Set footer
                embed.set_footer(text=f"Command ID: {interaction.id}")
                
                # Send the log
                await log_channel.send(embed=embed)
        except Exception as e:
            print(f"Error logging command: {e}")
            
    async def get_modlog_channel(self, guild):
        """Get the configured modlog channel for a guild"""
        try:
            # Check if config file exists
            if not os.path.exists('configs.json'):
                return None
                
            # Load config
            with open('configs.json', 'r') as f:
                configs = json.load(f)
                
            # Check if modlog and guilds sections exist
            if 'modlog' not in configs or 'guilds' not in configs['modlog']:
                return None
                
            # Get guild specific channel
            guild_id = str(guild.id)
            if guild_id in configs['modlog']['guilds']:
                channel_id = configs['modlog']['guilds'][guild_id]['channel_id']
                return guild.get_channel(channel_id)
                
            return None
        except Exception as e:
            print(f"Error getting modlog channel: {e}")
            return None

    @app_commands.command(name="warn", description="Warn a user and keep a record of the warning")
    @app_commands.default_permissions(ban_members=True)
    @app_commands.guild_only()
    async def warn(
        self, 
        interaction: discord.Interaction, 
        user: discord.Member, 
        reason: str
    ):
        """
        Warn a user and keep a record of the warning
        
        Parameters
        -----------
        user: The user to warn
        reason: The reason for the warning
        """
        # Check if user has ban permission
        if not interaction.user.guild_permissions.ban_members:
            return await interaction.response.send_message("You must have the 'Ban Members' permission to use this command.", ephemeral=True)
            
        # Can't warn yourself
        if user.id == interaction.user.id:
            return await interaction.response.send_message("You cannot warn yourself!", ephemeral=True)
            
        # Can't warn the bot
        if user.id == self.bot.user.id:
            return await interaction.response.send_message("You cannot warn the bot!", ephemeral=True)
            
        # Check if the user has higher authority
        if user.top_role.position >= interaction.user.top_role.position and interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message("You cannot warn someone with higher authority than you.", ephemeral=True)
            
        await interaction.response.defer(ephemeral=False)
        
        try:
            # Load existing warnings
            config_file = 'configs.json'
            warnings = await self.load_warnings(interaction.guild.id)
            
            # Get current time
            timestamp = int(discord.utils.utcnow().timestamp())
            
            # Create warning entry
            warning_id = f"{interaction.guild.id}-{user.id}-{timestamp}"
            warning_entry = {
                "id": warning_id,
                "user_id": user.id,
                "user_name": user.name,
                "guild_id": interaction.guild.id,
                "moderator_id": interaction.user.id,
                "moderator_name": interaction.user.name,
                "reason": reason,
                "timestamp": timestamp
            }
            
            # Add to warnings list
            user_id_str = str(user.id)
            if user_id_str not in warnings:
                warnings[user_id_str] = []
                
            warnings[user_id_str].append(warning_entry)
            
            # Save warnings
            await self.save_warnings(interaction.guild.id, warnings)
            
            # Create warning embed
            embed = discord.Embed(
                title="User Warned",
                description=f"{user.mention} has been warned.",
                color=discord.Color.orange()
            )
            embed.add_field(name="User", value=f"{user.mention} ({user.name})", inline=True)
            embed.add_field(name="Moderator", value=f"{interaction.user.mention}", inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Warning ID", value=warning_id, inline=False)
            embed.add_field(name="Total Warnings", value=str(len(warnings[user_id_str])), inline=True)
            embed.add_field(name="Date", value=f"<t:{timestamp}:F>", inline=True)
            
            # Set thumbnail to user avatar
            if user.avatar:
                embed.set_thumbnail(url=user.avatar.url)
                
            # Send the warning to the channel
            await interaction.followup.send(embed=embed)
            
            # Try to DM the user
            try:
                dm_embed = discord.Embed(
                    title="You've Been Warned",
                    description=f"You have received a warning in **{interaction.guild.name}**.",
                    color=discord.Color.orange()
                )
                dm_embed.add_field(name="Reason", value=reason, inline=False)
                dm_embed.add_field(name="Moderator", value=interaction.user.name, inline=True)
                dm_embed.add_field(name="Date", value=f"<t:{timestamp}:F>", inline=True)
                dm_embed.set_footer(text=f"Warning ID: {warning_id}")
                
                await user.send(embed=dm_embed)
            except:
                # Couldn't DM the user, continue anyway
                pass
                
            # Log to modlog channel if configured
            mod_log = await self.get_modlog_channel(interaction.guild)
            if mod_log:
                log_embed = discord.Embed(
                    title="User Warned",
                    description=f"{user.mention} has been warned by {interaction.user.mention}.",
                    color=discord.Color.orange(),
                    timestamp=discord.utils.utcnow()
                )
                log_embed.add_field(name="User", value=f"{user.mention} ({user.name})", inline=True)
                log_embed.add_field(name="User ID", value=user.id, inline=True)
                log_embed.add_field(name="Reason", value=reason, inline=False)
                log_embed.add_field(name="Warning ID", value=warning_id, inline=False)
                log_embed.add_field(name="Total Warnings", value=str(len(warnings[user_id_str])), inline=True)
                log_embed.set_footer(text=f"Warned by {interaction.user.name}")
                
                if user.avatar:
                    log_embed.set_thumbnail(url=user.avatar.url)
                    
                await mod_log.send(embed=log_embed)
            
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)
            
    @app_commands.command(name="deletewarn", description="Delete a warning from a user")
    @app_commands.default_permissions(ban_members=True)
    @app_commands.guild_only()
    async def deletewarn(
        self, 
        interaction: discord.Interaction, 
        warning_id: str
    ):
        """
        Delete a warning from a user
        
        Parameters
        -----------
        warning_id: The ID of the warning to delete
        """
        # Check if user has ban permission
        if not interaction.user.guild_permissions.ban_members:
            return await interaction.response.send_message("You must have the 'Ban Members' permission to use this command.", ephemeral=True)
            
        await interaction.response.defer(ephemeral=False)
        
        try:
            # Load existing warnings
            warnings = await self.load_warnings(interaction.guild.id)
            
            # Find the warning
            found = False
            user_id = None
            warning_data = None
            
            for uid, user_warnings in warnings.items():
                for i, warning in enumerate(user_warnings):
                    if warning["id"] == warning_id:
                        found = True
                        user_id = uid
                        warning_data = warning
                        # Remove the warning
                        warnings[uid].pop(i)
                        break
                if found:
                    break
                    
            if not found:
                return await interaction.followup.send(f"Warning with ID `{warning_id}` not found.", ephemeral=True)
                
            # Save the updated warnings
            await self.save_warnings(interaction.guild.id, warnings)
            
            # Try to get the user
            user = None
            try:
                user = await interaction.guild.fetch_member(int(user_id))
            except:
                # User might not be in the server anymore
                pass
                
            # Create embed response
            embed = discord.Embed(
                title="Warning Deleted",
                description=f"Warning `{warning_id}` has been deleted.",
                color=discord.Color.green()
            )
            
            if user:
                embed.add_field(name="User", value=f"{user.mention} ({user.name})", inline=True)
            else:
                embed.add_field(name="User ID", value=user_id, inline=True)
                
            embed.add_field(name="Moderator", value=f"{interaction.user.mention}", inline=True)
            embed.add_field(name="Original Reason", value=warning_data["reason"], inline=False)
            embed.add_field(name="Warning Date", value=f"<t:{warning_data['timestamp']}:F>", inline=False)
            
            # If warnings list is empty, remove the user
            if not warnings.get(user_id, []):
                remaining = 0
                if user_id in warnings:
                    del warnings[user_id]
            else:
                remaining = len(warnings.get(user_id, []))
                
            embed.add_field(name="Remaining Warnings", value=str(remaining), inline=True)
            
            await interaction.followup.send(embed=embed)
            
            # Log to modlog channel if configured
            mod_log = await self.get_modlog_channel(interaction.guild)
            if mod_log:
                log_embed = discord.Embed(
                    title="Warning Deleted",
                    description=f"Warning `{warning_id}` has been deleted by {interaction.user.mention}.",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow()
                )
                
                if user:
                    log_embed.add_field(name="User", value=f"{user.mention} ({user.name})", inline=True)
                else:
                    log_embed.add_field(name="User ID", value=user_id, inline=True)
                    
                log_embed.add_field(name="Original Reason", value=warning_data["reason"], inline=False)
                log_embed.add_field(name="Warning Date", value=f"<t:{warning_data['timestamp']}:F>", inline=False)
                log_embed.add_field(name="Remaining Warnings", value=str(remaining), inline=True)
                log_embed.set_footer(text=f"Deleted by {interaction.user.name}")
                
                await mod_log.send(embed=log_embed)
            
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)
            
    @app_commands.command(name="showwarns", description="Show warnings for a user")
    @app_commands.default_permissions(ban_members=True)
    @app_commands.guild_only()
    async def showwarns(
        self, 
        interaction: discord.Interaction, 
        user: discord.Member
    ):
        """
        Show warnings for a user
        
        Parameters
        -----------
        user: The user to show warnings for
        """
        # Check if user has ban permission
        if not interaction.user.guild_permissions.ban_members:
            return await interaction.response.send_message("You must have the 'Ban Members' permission to use this command.", ephemeral=True)
            
        await interaction.response.defer(ephemeral=False)
        
        try:
            # Load warnings
            warnings = await self.load_warnings(interaction.guild.id)
            
            # Get user warnings
            user_id = str(user.id)
            user_warnings = warnings.get(user_id, [])
            
            if not user_warnings:
                embed = discord.Embed(
                    title="User Warnings",
                    description=f"{user.mention} has no warnings.",
                    color=discord.Color.green()
                )
                embed.set_footer(text=f"User ID: {user.id}")
                if user.avatar:
                    embed.set_thumbnail(url=user.avatar.url)
                return await interaction.followup.send(embed=embed)
                
            # Create embed
            embed = discord.Embed(
                title="User Warnings",
                description=f"{user.mention} has {len(user_warnings)} warning(s).",
                color=discord.Color.orange()
            )
            
            # Sort warnings by timestamp (newest first)
            user_warnings.sort(key=lambda w: w["timestamp"], reverse=True)
            
            # Add each warning
            for i, warning in enumerate(user_warnings, 1):
                # Get moderator if available
                mod_id = warning.get("moderator_id")
                mod_name = warning.get("moderator_name", "Unknown Moderator")
                moderator = f"<@{mod_id}> ({mod_name})" if mod_id else mod_name
                
                # Format the warning entry
                value = f"**Reason:** {warning['reason']}\n"
                value += f"**Moderator:** {moderator}\n"
                value += f"**Date:** <t:{warning['timestamp']}:F>\n"
                value += f"**ID:** `{warning['id']}`"
                
                embed.add_field(
                    name=f"Warning #{i}", 
                    value=value, 
                    inline=False
                )
                
            embed.set_footer(text=f"User ID: {user.id} • Use /deletewarn [warning_id] to remove a warning")
            
            if user.avatar:
                embed.set_thumbnail(url=user.avatar.url)
                
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)
            
    async def load_warnings(self, guild_id):
        """Load warnings for a guild from the config file"""
        try:
            config_file = 'configs.json'
            if not os.path.exists(config_file):
                return {}
                
            with open(config_file, 'r') as f:
                configs = json.load(f)
                
            # Initialize or get warnings section
            if 'warnings' not in configs:
                configs['warnings'] = {}
                
            # Initialize or get guild warnings
            guild_id_str = str(guild_id)
            if guild_id_str not in configs['warnings']:
                configs['warnings'][guild_id_str] = {}
                
            return configs['warnings'][guild_id_str]
        except Exception as e:
            print(f"Error loading warnings: {e}")
            return {}
            
    async def save_warnings(self, guild_id, warnings_data):
        """Save warnings for a guild to the config file"""
        try:
            config_file = 'configs.json'
            
            # Create configs directory if it doesn't exist
            os.makedirs('configs', exist_ok=True)
            
            # Load existing config or create new
            configs = {}
            if os.path.exists(config_file):
                try:
                    with open(config_file, 'r') as f:
                        configs = json.load(f)
                except json.JSONDecodeError:
                    configs = {}
                    
            # Initialize warnings section if not exists
            if 'warnings' not in configs:
                configs['warnings'] = {}
                
            # Save guild warnings
            guild_id_str = str(guild_id)
            configs['warnings'][guild_id_str] = warnings_data
            
            # Write config
            with open(config_file, 'w') as f:
                json.dump(configs, f, indent=4)
                
            return True
        except Exception as e:
            print(f"Error saving warnings: {e}")
            return False

    @app_commands.command(name="dm", description="Send a direct message to a user through the bot")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def dm(
        self, 
        interaction: discord.Interaction, 
        user: discord.Member, 
        message: str,
        anonymous: bool = False
    ):
        """
        Send a direct message to a user through the bot
        
        Parameters
        -----------
        user: The user to send the message to
        message: The message content to send
        anonymous: Whether to hide the sender's identity (default: False)
        """
        # Check if user has administrator permission
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("You must have the 'Administrator' permission to use this command.", ephemeral=True)
            
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Create an embed for the DM
            embed = discord.Embed(
                title="Message from Server Staff",
                description=message,
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            
            # Add server info
            embed.add_field(name="Server", value=interaction.guild.name, inline=True)
            
            # Set footer with sender info if not anonymous
            if not anonymous:
                embed.add_field(name="Sent by", value=f"{interaction.user.name}", inline=True)
                embed.set_footer(text=f"Message ID: {interaction.id}")
            else:
                embed.set_footer(text=f"Server: {interaction.guild.name}")
            
            # Add server icon if available
            if interaction.guild.icon:
                embed.set_thumbnail(url=interaction.guild.icon.url)
                
            # Try to send the DM
            try:
                await user.send(embed=embed)
                
                # Create success response
                success_embed = discord.Embed(
                    title="Direct Message Sent",
                    description=f"Your message has been sent to {user.mention}.",
                    color=discord.Color.green()
                )
                success_embed.add_field(name="Message", value=message if len(message) <= 1024 else f"{message[:1021]}...", inline=False)
                success_embed.add_field(name="Anonymous", value="Yes" if anonymous else "No", inline=True)
                
                await interaction.followup.send(embed=success_embed, ephemeral=True)
                
                # Log to modlog channel if configured
                mod_log = await self.get_modlog_channel(interaction.guild)
                if mod_log:
                    log_embed = discord.Embed(
                        title="Direct Message Sent",
                        description=f"{interaction.user.mention} sent a DM to {user.mention}.",
                        color=discord.Color.blue(),
                        timestamp=discord.utils.utcnow()
                    )
                    log_embed.add_field(name="Message", value=message if len(message) <= 1024 else f"{message[:1021]}...", inline=False)
                    log_embed.add_field(name="Anonymous", value="Yes" if anonymous else "No", inline=True)
                    log_embed.add_field(name="User ID", value=user.id, inline=True)
                    log_embed.set_footer(text=f"Sent by {interaction.user.name} ({interaction.user.id})")
                    
                    await mod_log.send(embed=log_embed)
                
            except discord.Forbidden:
                # User has DMs closed or has blocked the bot
                await interaction.followup.send(f"Could not send DM to {user.mention}. They may have DMs disabled or have blocked the bot.", ephemeral=True)
                
            except Exception as e:
                await interaction.followup.send(f"An error occurred while sending the DM: {str(e)}", ephemeral=True)
                
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)

    @app_commands.command(name="mute", description="Mute a user for a specified duration")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.guild_only()
    async def mute(
        self, 
        interaction: discord.Interaction, 
        user: discord.Member, 
        duration: str = None,
        reason: str = None
    ):
        """
        Mute a user for a specified duration
        
        Parameters
        -----------
        user: The user to mute
        duration: Mute duration (e.g. 1d, 12h, 30m, 1d12h30m). Leave empty for indefinite mute
        reason: Reason for the mute
        """
        # Check if the bot has permission to moderate members
        if not interaction.guild.me.guild_permissions.moderate_members:
            return await interaction.response.send_message("Bot has no permission to moderate members.", ephemeral=True)
        
        # Check if user has permission to moderate members
        if not interaction.user.guild_permissions.moderate_members:
            return await interaction.response.send_message("You need 'Moderate Members' permission to use this command.", ephemeral=True)
        
        # User can't mute themselves
        if user.id == interaction.user.id:
            return await interaction.response.send_message("You cannot mute yourself!", ephemeral=True)
        
        # User can't mute the bot
        if user.id == self.bot.user.id:
            return await interaction.response.send_message("You cannot mute me!", ephemeral=True)
        
        # Check if the user to be muted has higher authority
        if user.top_role.position >= interaction.user.top_role.position and interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message("You cannot mute someone with higher authority than you.", ephemeral=True)
        
        # Check if the user to be muted has higher authority than the bot
        if user.top_role.position >= interaction.guild.me.top_role.position:
            return await interaction.response.send_message("I cannot mute someone with higher authority than me.", ephemeral=True)
        
        await interaction.response.defer(ephemeral=False)
        
        # Parse duration
        seconds = 0
        mute_until = None
        if duration:
            pattern = re.compile(r'(\d+)([smhdw])')
            matches = pattern.findall(duration.lower())
            
            if not matches:
                return await interaction.followup.send(
                    "Invalid duration format. Examples: `30m`, `1h`, `1d`, `1w`, `1d12h30m`", 
                    ephemeral=True
                )
            
            time_mapping = {
                's': 1,             # seconds
                'm': 60,            # minutes
                'h': 3600,          # hours
                'd': 86400,         # days
                'w': 604800         # weeks
            }
            
            for value, unit in matches:
                seconds += int(value) * time_mapping[unit]
            
            if seconds < 60 and seconds > 0:
                return await interaction.followup.send("Duration must be at least 1 minute.", ephemeral=True)
            
            if seconds > 2419200:  # 28 days (Discord's maximum timeout duration)
                return await interaction.followup.send("Duration cannot exceed 28 days (Discord's limitation).", ephemeral=True)
            
            # Calculate mute end time
            mute_until = discord.utils.utcnow() + datetime.timedelta(seconds=seconds)

        try:
            # Create a muted role if it doesn't exist
            muted_role = discord.utils.get(interaction.guild.roles, name="Muted")
            
            if not muted_role:
                try:
                    # Create the Muted role
                    muted_role = await interaction.guild.create_role(
                        name="Muted",
                        reason="Automatically created for mute command",
                        color=discord.Color.dark_gray()
                    )
                    
                    # Place it just below the bot's highest role
                    try:
                        positions = {
                            muted_role: interaction.guild.me.top_role.position - 1
                        }
                        await interaction.guild.edit_role_positions(positions=positions)
                    except:
                        pass  # Role positioning failed, but that's not critical
                    
                    # Set permissions for all text channels
                    for channel in interaction.guild.channels:
                        if isinstance(channel, discord.TextChannel) or isinstance(channel, discord.VoiceChannel) or isinstance(channel, discord.CategoryChannel):
                            try:
                                await channel.set_permissions(
                                    muted_role,
                                    send_messages=False,
                                    add_reactions=False,
                                    speak=False,
                                    stream=False,
                                    connect=False
                                )
                            except:
                                continue  # Skip channels where permission setting fails
                except discord.Forbidden:
                    return await interaction.followup.send("I don't have permission to create a Muted role.", ephemeral=True)
            
            # Add the muted role to the user
            await user.add_roles(muted_role, reason=f"Muted by {interaction.user}: {reason}" if reason else f"Muted by {interaction.user}")
            
            # Also apply Discord's timeout feature if duration is specified and within limits
            if seconds > 0 and seconds <= 2419200:  # 28 days max
                await user.timeout(datetime.timedelta(seconds=seconds), reason=f"Muted by {interaction.user}: {reason}" if reason else f"Muted by {interaction.user}")
                
            # Format the duration for display
            if duration:
                duration_delta = datetime.timedelta(seconds=seconds)
                formatted_duration = self.format_timedelta(duration_delta)
            else:
                formatted_duration = "Indefinite"
            
            # Create embed response
            embed = discord.Embed(
                title="User Muted",
                description=f"{user.mention} has been muted.",
                color=discord.Color.red()
            )
            
            embed.add_field(name="User", value=f"{user.mention} ({user.name})", inline=True)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            embed.add_field(name="Duration", value=formatted_duration, inline=True)
            
            if reason:
                embed.add_field(name="Reason", value=reason, inline=False)
                
            if mute_until:
                embed.add_field(name="Muted Until", value=f"<t:{int(mute_until.timestamp())}:F>", inline=False)
                
            if user.avatar:
                embed.set_thumbnail(url=user.avatar.url)
                
            await interaction.followup.send(embed=embed)
            
            # Try to DM the user
            try:
                dm_embed = discord.Embed(
                    title="You Have Been Muted",
                    description=f"You have been muted in **{interaction.guild.name}**.",
                    color=discord.Color.red()
                )
                
                dm_embed.add_field(name="Duration", value=formatted_duration, inline=True)
                if reason:
                    dm_embed.add_field(name="Reason", value=reason, inline=False)
                    
                if mute_until:
                    dm_embed.add_field(name="Muted Until", value=f"<t:{int(mute_until.timestamp())}:F>", inline=False)
                    
                if interaction.guild.icon:
                    dm_embed.set_thumbnail(url=interaction.guild.icon.url)
                    
                await user.send(embed=dm_embed)
            except:
                # Couldn't DM the user, continue anyway
                pass
                
            # Log to modlog channel if configured
            mod_log = await self.get_modlog_channel(interaction.guild)
            if mod_log:
                log_embed = discord.Embed(
                    title="User Muted",
                    description=f"{user.mention} was muted by {interaction.user.mention}.",
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow()
                )
                
                log_embed.add_field(name="User", value=f"{user.mention} ({user.name})", inline=True)
                log_embed.add_field(name="User ID", value=user.id, inline=True)
                log_embed.add_field(name="Duration", value=formatted_duration, inline=True)
                
                if reason:
                    log_embed.add_field(name="Reason", value=reason, inline=False)
                    
                if mute_until:
                    log_embed.add_field(name="Muted Until", value=f"<t:{int(mute_until.timestamp())}:F>", inline=False)
                    
                log_embed.set_footer(text=f"Moderator: {interaction.user.name} ({interaction.user.id})")
                
                if user.avatar:
                    log_embed.set_thumbnail(url=user.avatar.url)
                    
                await mod_log.send(embed=log_embed)
                
        except discord.Forbidden:
            await interaction.followup.send("I don't have permission to mute this user.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)

    @app_commands.command(name="unmute", description="Unmute a previously muted user")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.guild_only()
    async def unmute(
        self, 
        interaction: discord.Interaction, 
        user: discord.Member, 
        reason: str = None
    ):
        """
        Unmute a previously muted user
        
        Parameters
        -----------
        user: The user to unmute
        reason: Reason for the unmute
        """
        # Check if the bot has permission to moderate members
        if not interaction.guild.me.guild_permissions.moderate_members:
            return await interaction.response.send_message("Bot has no permission to moderate members.", ephemeral=True)
        
        # Check if user has permission to moderate members
        if not interaction.user.guild_permissions.moderate_members:
            return await interaction.response.send_message("You need 'Moderate Members' permission to use this command.", ephemeral=True)
        
        await interaction.response.defer(ephemeral=False)
        
        try:
            # Find the muted role
            muted_role = discord.utils.get(interaction.guild.roles, name="Muted")
            
            is_muted = False
            
            # Remove the muted role if the user has it
            if muted_role and muted_role in user.roles:
                await user.remove_roles(muted_role, reason=f"Unmuted by {interaction.user}: {reason}" if reason else f"Unmuted by {interaction.user}")
                is_muted = True
                
            # Remove Discord's timeout if active
            if user.is_timed_out():
                await user.timeout(None, reason=f"Unmuted by {interaction.user}: {reason}" if reason else f"Unmuted by {interaction.user}")
                is_muted = True
                
            if not is_muted:
                return await interaction.followup.send(f"{user.mention} is not muted.", ephemeral=True)
                
            # Create embed response
            embed = discord.Embed(
                title="User Unmuted",
                description=f"{user.mention} has been unmuted.",
                color=discord.Color.green()
            )
            
            embed.add_field(name="User", value=f"{user.mention} ({user.name})", inline=True)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            
            if reason:
                embed.add_field(name="Reason", value=reason, inline=False)
                
            if user.avatar:
                embed.set_thumbnail(url=user.avatar.url)
                
            await interaction.followup.send(embed=embed)
            
            # Try to DM the user
            try:
                dm_embed = discord.Embed(
                    title="You Have Been Unmuted",
                    description=f"You have been unmuted in **{interaction.guild.name}**.",
                    color=discord.Color.green()
                )
                
                if reason:
                    dm_embed.add_field(name="Reason", value=reason, inline=False)
                    
                if interaction.guild.icon:
                    dm_embed.set_thumbnail(url=interaction.guild.icon.url)
                    
                await user.send(embed=dm_embed)
            except:
                # Couldn't DM the user, continue anyway
                pass
                
            # Log to modlog channel if configured
            mod_log = await self.get_modlog_channel(interaction.guild)
            if mod_log:
                log_embed = discord.Embed(
                    title="User Unmuted",
                    description=f"{user.mention} was unmuted by {interaction.user.mention}.",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow()
                )
                
                log_embed.add_field(name="User", value=f"{user.mention} ({user.name})", inline=True)
                log_embed.add_field(name="User ID", value=user.id, inline=True)
                
                if reason:
                    log_embed.add_field(name="Reason", value=reason, inline=False)
                    
                log_embed.set_footer(text=f"Moderator: {interaction.user.name} ({interaction.user.id})")
                
                if user.avatar:
                    log_embed.set_thumbnail(url=user.avatar.url)
                    
                await mod_log.send(embed=log_embed)
                
        except discord.Forbidden:
            await interaction.followup.send("I don't have permission to unmute this user.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)

    @app_commands.command(name="announce", description="Send an announcement message to a channel")
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.guild_only()
    async def announce(
        self, 
        interaction: discord.Interaction, 
        channel: discord.TextChannel, 
        title: str,
        message: str,
        color: str = "blue",
        mention: str = None
    ):
        """
        Send an announcement message to a channel
        
        Parameters
        -----------
        channel: The channel to send the announcement to
        title: The title of the announcement
        message: The content of the announcement (supports Markdown)
        color: Color of the embed (red, green, blue, orange, gold, purple)
        mention: Role or @everyone to mention with the announcement (optional)
        """
        # Check if user has permission to manage messages
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("You need 'Manage Messages' permission to use this command.", ephemeral=True)
            
        # Check if the bot has permission to send messages in the channel
        if not channel.permissions_for(interaction.guild.me).send_messages:
            return await interaction.response.send_message(f"Bot cannot send messages in {channel.mention}. Please check permissions.", ephemeral=True)
            
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Process color
            embed_color = discord.Color.blue()  # Default color
            color = color.lower()
            
            color_map = {
                "red": discord.Color.red(),
                "green": discord.Color.green(),
                "blue": discord.Color.blue(),
                "orange": discord.Color(0xFFA500),
                "gold": discord.Color(0xFFD700),
                "purple": discord.Color.purple(),
                "yellow": discord.Color.yellow(),
                "black": discord.Color(0x000000),
                "white": discord.Color(0xFFFFFF),
                "pink": discord.Color(0xFFC0CB),
                "cyan": discord.Color(0x00FFFF),
                "teal": discord.Color.teal(),
            }
            
            if color in color_map:
                embed_color = color_map[color]
            elif color.startswith('#'):
                # Hex color code
                try:
                    hex_color = color[1:] if color.startswith('#') else color
                    embed_color = discord.Color(int(hex_color, 16))
                except:
                    # Invalid hex color, use default
                    pass
                    
            # Create the embed
            embed = discord.Embed(
                title=title,
                description=message,
                color=embed_color,
                timestamp=discord.utils.utcnow()
            )
            
            embed.set_footer(text=f"Announcement by {interaction.user.name}")
            
            # Add server icon if available
            if interaction.guild.icon:
                embed.set_thumbnail(url=interaction.guild.icon.url)
                
            # Process mention
            mention_text = ""
            if mention:
                # Check if it's a role mention
                if mention.lower() == "everyone":
                    # Check if the bot has permission to mention everyone
                    if channel.permissions_for(interaction.guild.me).mention_everyone:
                        mention_text = "@everyone"
                    else:
                        await interaction.followup.send("I don't have permission to mention everyone in that channel.", ephemeral=True)
                        
                elif mention.lower() == "here":
                    # Check if the bot has permission to mention everyone
                    if channel.permissions_for(interaction.guild.me).mention_everyone:
                        mention_text = "@here"
                    else:
                        await interaction.followup.send("I don't have permission to mention here in that channel.", ephemeral=True)
                        
                else:
                    # Try to find the role
                    try:
                        role_id = int(mention.strip('<@&>'))
                        role = interaction.guild.get_role(role_id)
                        
                        if role:
                            # Check if the role is mentionable or the bot has permission to mention all roles
                            if role.mentionable or channel.permissions_for(interaction.guild.me).mention_everyone:
                                mention_text = role.mention
                            else:
                                await interaction.followup.send(f"The role {role.name} is not mentionable and I don't have permission to mention all roles.", ephemeral=True)
                    except ValueError:
                        # Not a role ID, try to find by name
                        role = discord.utils.get(interaction.guild.roles, name=mention)
                        if role:
                            # Check if the role is mentionable
                            if role.mentionable or channel.permissions_for(interaction.guild.me).mention_everyone:
                                mention_text = role.mention
                            else:
                                await interaction.followup.send(f"The role {role.name} is not mentionable and I don't have permission to mention all roles.", ephemeral=True)
                        else:
                            await interaction.followup.send(f"Could not find a role named '{mention}'.", ephemeral=True)
                            
            # Send the announcement
            if mention_text:
                announcement_msg = await channel.send(content=mention_text, embed=embed)
            else:
                announcement_msg = await channel.send(embed=embed)
                
            # Success message
            success_embed = discord.Embed(
                title="Announcement Sent",
                description=f"Announcement has been sent to {channel.mention}.",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            
            success_embed.add_field(name="Title", value=title, inline=False)
            
            # Add link to the message
            success_embed.add_field(name="Message Link", value=f"[Click to view]({announcement_msg.jump_url})", inline=False)
            
            await interaction.followup.send(embed=success_embed, ephemeral=True)
            
            # Log to modlog channel if configured
            mod_log = await self.get_modlog_channel(interaction.guild)
            if mod_log:
                log_embed = discord.Embed(
                    title="Announcement Sent",
                    description=f"An announcement was sent to {channel.mention} by {interaction.user.mention}.",
                    color=embed_color,
                    timestamp=discord.utils.utcnow()
                )
                
                log_embed.add_field(name="Title", value=title, inline=False)
                log_embed.add_field(name="Message Link", value=f"[Click to view]({announcement_msg.jump_url})", inline=False)
                
                log_embed.set_footer(text=f"Sent by {interaction.user.name} ({interaction.user.id})")
                
                await mod_log.send(embed=log_embed)
                
        except discord.Forbidden:
            await interaction.followup.send("I don't have permission to send messages in that channel.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))