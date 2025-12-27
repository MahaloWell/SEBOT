"""Game setup commands - creation, configuration, and channel management."""

import discord
from discord import app_commands
from discord.ext import commands

from helpers.game_state import games, get_game, create_game, Game, Player
from helpers.permissions import is_gm_or_im, gm_only, require_game, get_gm_role, get_im_role


class SetupCog(commands.Cog):
    """Commands for setting up and configuring games."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.command(name="create_game", description="[GM/IM] Create a new elimination game in this server")
    @gm_only()
    async def create_game_cmd(self, interaction: discord.Interaction):
        """Create a new game in this server."""
        guild_id = interaction.guild_id
        
        if guild_id in games:
            await interaction.response.send_message(
                "⚠️ A game already exists in this server! Use `/end_game` to end it first.",
                ephemeral=True
            )
            return
        
        create_game(guild_id, interaction.user.id)
        
        await interaction.response.send_message(
            f"✅ **Game Created!**\n"
            f"Game Master: {interaction.user.mention}\n"
            f"Status: Setup Phase\n\n"
            f"**Next steps:**\n"
            f"1. `/set_game_name` - Set game tag and flavor name\n"
            f"2. `/create_game_channel` OR `/set_game_channel` - Set up game channel\n"
            f"3. `/config_game` - Configure settings (anon mode, day/night length, etc.)\n"
            f"4. Players join with `/join_game`\n"
            f"5. `/assign_role` or `/randomize_alignments` - Assign roles\n"
            f"6. `/start_game` - Begin the game"
        )
    
    @app_commands.command(name="set_game_name", description="[GM/IM] Set the game tag and flavor name")
    @app_commands.describe(
        game_tag="Game tag (e.g., LG042, MR015, QF008)",
        flavor_name="Flavor/theme name (e.g., 'A Tale of Rats and Spores')"
    )
    @gm_only()
    @require_game()
    async def set_game_name(self, interaction: discord.Interaction, game_tag: str, flavor_name: str):
        """Set game identification."""
        game = get_game(interaction.guild_id)
        game.game_tag = game_tag
        game.flavor_name = flavor_name
        
        await interaction.response.send_message(
            f"✅ **Game Named:**\n"
            f"**Tag:** {game_tag}\n"
            f"**Flavor:** {flavor_name}"
        )
    
    @app_commands.command(name="create_game_channel", description="[GM/IM] Create a new game discussion channel")
    @gm_only()
    @require_game()
    async def create_game_channel(self, interaction: discord.Interaction):
        """Bot creates the game channel automatically."""
        game = get_game(interaction.guild_id)
        
        if game.channels.game_channel_id:
            await interaction.response.send_message("⚠️ Game channel already set!", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        guild = interaction.guild
        gm_role = get_gm_role(guild)
        im_role = get_im_role(guild)
        
        # Create channel with public read, restricted write
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=False,
                create_public_threads=False,
                create_private_threads=False
            ),
            guild.me: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                create_public_threads=True,
                create_private_threads=True
            )
        }
        
        for role in [gm_role, im_role]:
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    create_public_threads=True,
                    create_private_threads=True
                )
        
        # Generate channel name
        if game.game_tag and game.flavor_name:
            clean_flavor = game.flavor_name.lower().replace(' ', '-').replace("'", '').replace('"', '')
            channel_name = f"{game.game_tag.lower()}-{clean_flavor}"
        elif game.game_tag:
            channel_name = game.game_tag.lower()
        else:
            channel_name = "elimination-game"
        
        game_channel = await guild.create_text_channel(
            name=channel_name,
            overwrites=overwrites,
            topic=f"{game.flavor_name or 'Elimination Game'} - Discussion Channel"
        )
        
        game.channels.game_channel_id = game_channel.id
        
        await interaction.followup.send(
            f"✅ Created game channel: {game_channel.mention}\n"
            f"Channel is public (everyone can read), but only GM/IM can post until game starts."
        )
    
    @app_commands.command(name="set_game_channel", description="[GM/IM] Use an existing channel as the game channel")
    @app_commands.describe(channel="The channel where the game will be played")
    @gm_only()
    @require_game()
    async def set_game_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Set which channel is the main game channel."""
        game = get_game(interaction.guild_id)
        game.channels.game_channel_id = channel.id
        
        await interaction.response.send_message(
            f"✅ Game channel set to {channel.mention}\n"
            f"⚠️ Note: You'll need to manually configure permissions for this channel."
        )
    
    @app_commands.command(name="config_game", description="[GM/IM] Configure game settings")
    @app_commands.describe(
        day_length="Length of day phases (use with day_unit)",
        day_unit="Time unit for day length: 'minutes' or 'hours'",
        night_length="Length of night phases (use with night_unit)",
        night_unit="Time unit for night length: 'minutes' or 'hours'",
        win_condition="Elims win condition: 'parity', 'overparity', or 'last_man_standing'",
        anon_mode="Enable anonymous mode: True or False",
        auto_phase_transition="Enable automatic phase transitions: True or False",
        allow_no_elimination="Allow voting for no elimination: True or False",
        min_votes_to_eliminate="Minimum votes to eliminate (0=plurality, -1=force RNG if 0 votes)",
        pms_enabled="Allow players to PM each other: True or False",
        gms_see_pms="GMs/IMs can see PM threads: True or False",
        village_name="Display name for village faction (e.g., 'Village', 'Town')",
        elim_name="Display name for eliminator faction (e.g., 'Elims', 'Spiked', 'Mafia')",
        game_mode="Game mode: 'all' (any role) or 'tyrian' (Mistborn roles)",
        seeker_mode="What Seeker reveals: 'role_only', 'alignment_only', or 'both'",
        thug_mode="Thug protection: 'survive', 'delayed_phase', or 'delayed_cycle'",
        coinshot_ammo="Coinshot kill limit (0=unlimited, positive=max kills per Coinshot)",
        smoker_phase="When Smoker can change target: 'day', 'night', or 'both'",
        tineye_phase="When Tineye can submit message: 'day', 'night', or 'both'"
    )
    @app_commands.choices(
        day_unit=[
            app_commands.Choice(name="Minutes", value="minutes"),
            app_commands.Choice(name="Hours", value="hours")
        ],
        night_unit=[
            app_commands.Choice(name="Minutes", value="minutes"),
            app_commands.Choice(name="Hours", value="hours")
        ]
    )
    @gm_only()
    @require_game()
    async def config_game(
        self,
        interaction: discord.Interaction,
        day_length: int = None,
        day_unit: app_commands.Choice[str] = None,
        night_length: int = None,
        night_unit: app_commands.Choice[str] = None,
        win_condition: str = None,
        anon_mode: bool = None,
        auto_phase_transition: bool = None,
        allow_no_elimination: bool = None,
        min_votes_to_eliminate: int = None,
        pms_enabled: bool = None,
        gms_see_pms: bool = None,
        village_name: str = None,
        elim_name: str = None,
        game_mode: str = None,
        seeker_mode: str = None,
        thug_mode: str = None,
        coinshot_ammo: int = None,
        smoker_phase: str = None,
        tineye_phase: str = None
    ):
        """Configure game settings."""
        game = get_game(interaction.guild_id)
        
        # Allow changing auto_phase_transition during active game
        if game.status != 'setup':
            if auto_phase_transition is not None:
                game.config.auto_phase_transition = auto_phase_transition
                await interaction.response.send_message(
                    f"✅ Automatic phase transitions: {'Enabled' if auto_phase_transition else 'Disabled'}"
                )
                return
            else:
                await interaction.response.send_message(
                    "❌ Cannot change settings after game has started (except auto_phase_transition)!",
                    ephemeral=True
                )
                return
        
        changes = []
        
        # Day length
        if day_length is not None:
            if day_unit is None:
                await interaction.response.send_message(
                    "❌ You must specify day_unit (minutes or hours) when setting day_length!",
                    ephemeral=True
                )
                return
            
            if day_unit.value == "hours":
                game.config.day_length_minutes = day_length * 60
                changes.append(f"Day length: {day_length} hours")
            else:
                game.config.day_length_minutes = day_length
                changes.append(f"Day length: {day_length} minutes")
        
        # Night length
        if night_length is not None:
            if night_unit is None:
                await interaction.response.send_message(
                    "❌ You must specify night_unit (minutes or hours) when setting night_length!",
                    ephemeral=True
                )
                return
            
            if night_unit.value == "hours":
                game.config.night_length_minutes = night_length * 60
                changes.append(f"Night length: {night_length} hours")
            else:
                game.config.night_length_minutes = night_length
                changes.append(f"Night length: {night_length} minutes")
        
        if win_condition is not None:
            if win_condition.lower() not in ['parity', 'overparity', 'last_man_standing']:
                await interaction.response.send_message(
                    "❌ Win condition must be 'parity', 'overparity', or 'last_man_standing'",
                    ephemeral=True
                )
                return
            game.config.win_condition = win_condition.lower()
            changes.append(f"Win condition: {win_condition}")
        
        if anon_mode is not None:
            game.config.anon_mode = anon_mode
            changes.append(f"Anonymous mode: {'Enabled' if anon_mode else 'Disabled'}")
        
        if auto_phase_transition is not None:
            game.config.auto_phase_transition = auto_phase_transition
            changes.append(f"Auto phase transitions: {'Enabled' if auto_phase_transition else 'Disabled'}")
        
        if allow_no_elimination is not None:
            game.config.allow_no_elimination = allow_no_elimination
            changes.append(f"Allow no elimination: {'Enabled' if allow_no_elimination else 'Disabled'}")
        
        if min_votes_to_eliminate is not None:
            if min_votes_to_eliminate < -1:
                await interaction.response.send_message(
                    "❌ min_votes_to_eliminate must be -1 or greater!",
                    ephemeral=True
                )
                return
            game.config.min_votes_to_eliminate = min_votes_to_eliminate
            if min_votes_to_eliminate == 0:
                changes.append("Minimum votes: Plurality (highest count wins)")
            elif min_votes_to_eliminate == -1:
                changes.append("Minimum votes: Force RNG if no votes")
            else:
                changes.append(f"Minimum votes: {min_votes_to_eliminate}")
        
        if pms_enabled is not None:
            game.config.pms_enabled = pms_enabled
            changes.append(f"Player PMs: {'Enabled' if pms_enabled else 'Disabled'}")
        
        if gms_see_pms is not None:
            game.config.gms_see_pms = gms_see_pms
            changes.append(f"GMs see PMs: {'Yes' if gms_see_pms else 'No'}")
        
        if village_name is not None:
            game.config.village_name = village_name
            changes.append(f"Village faction name: {village_name}")
        
        if elim_name is not None:
            game.config.elim_name = elim_name
            changes.append(f"Eliminator faction name: {elim_name}")
        
        if game_mode is not None:
            if game_mode.lower() not in ['all', 'tyrian']:
                await interaction.response.send_message(
                    "❌ Game mode must be 'all' or 'tyrian'",
                    ephemeral=True
                )
                return
            game.roles.game_mode = game_mode.lower()
            changes.append(f"Game mode: {game_mode}")
        
        if seeker_mode is not None:
            if seeker_mode.lower() not in ['role_only', 'alignment_only', 'both']:
                await interaction.response.send_message(
                    "❌ Seeker mode must be 'role_only', 'alignment_only', or 'both'",
                    ephemeral=True
                )
                return
            game.roles.seeker_mode = seeker_mode.lower()
            changes.append(f"Seeker mode: {seeker_mode}")
        
        if thug_mode is not None:
            if thug_mode.lower() not in ['survive', 'delayed_phase', 'delayed_cycle']:
                await interaction.response.send_message(
                    "❌ Thug mode must be 'survive', 'delayed_phase', or 'delayed_cycle'",
                    ephemeral=True
                )
                return
            game.roles.thug_mode = thug_mode.lower()
            changes.append(f"Thug mode: {thug_mode}")
        
        if coinshot_ammo is not None:
            if coinshot_ammo < 0:
                await interaction.response.send_message(
                    "❌ Coinshot ammo must be 0 (unlimited) or a positive number",
                    ephemeral=True
                )
                return
            game.roles.coinshot_ammo = coinshot_ammo
            if coinshot_ammo == 0:
                changes.append("Coinshot ammo: Unlimited")
            else:
                changes.append(f"Coinshot ammo: {coinshot_ammo} kill(s)")
        
        if smoker_phase is not None:
            if smoker_phase.lower() not in ['day', 'night', 'both']:
                await interaction.response.send_message(
                    "❌ Smoker phase must be 'day', 'night', or 'both'",
                    ephemeral=True
                )
                return
            game.roles.smoker_phase = smoker_phase.lower()
            changes.append(f"Smoker phase: {smoker_phase}")
        
        if tineye_phase is not None:
            if tineye_phase.lower() not in ['day', 'night', 'both']:
                await interaction.response.send_message(
                    "❌ Tineye phase must be 'day', 'night', or 'both'",
                    ephemeral=True
                )
                return
            game.roles.tineye_phase = tineye_phase.lower()
            changes.append(f"Tineye phase: {tineye_phase}")
        
        if not changes:
            # Show current settings
            day_display = f"{game.config.day_length_minutes // 60} hours" if game.config.day_length_minutes >= 60 else f"{game.config.day_length_minutes} minutes"
            night_display = f"{game.config.night_length_minutes // 60} hours" if game.config.night_length_minutes >= 60 else f"{game.config.night_length_minutes} minutes"
            
            if game.config.min_votes_to_eliminate == 0:
                min_votes_display = "Plurality (highest count wins)"
            elif game.config.min_votes_to_eliminate == -1:
                min_votes_display = "Force RNG if no votes"
            else:
                min_votes_display = str(game.config.min_votes_to_eliminate)
            
            coinshot_display = "Unlimited" if game.roles.coinshot_ammo == 0 else f"{game.roles.coinshot_ammo} kill(s)"
            
            await interaction.response.send_message(
                f"**⚙️ Current Game Settings:**\n"
                f"• Game Tag: {game.game_tag or 'Not set'}\n"
                f"• Flavor: {game.flavor_name or 'Not set'}\n"
                f"• Game Mode: {game.roles.game_mode}\n"
                f"• Day length: {day_display}\n"
                f"• Night length: {night_display}\n"
                f"• Win condition: {game.config.win_condition}\n"
                f"• Anonymous mode: {'Enabled' if game.config.anon_mode else 'Disabled'}\n"
                f"• Auto phase transitions: {'Enabled' if game.config.auto_phase_transition else 'Disabled'}\n"
                f"• Allow no elimination: {'Enabled' if game.config.allow_no_elimination else 'Disabled'}\n"
                f"• Minimum votes: {min_votes_display}\n"
                f"• Player PMs: {'Enabled' if game.config.pms_enabled else 'Disabled'}\n"
                f"• GMs see PMs: {'Yes' if game.config.gms_see_pms else 'No'}\n"
                f"• Seeker mode: {game.roles.seeker_mode}\n"
                f"• Thug mode: {game.roles.thug_mode}\n"
                f"• Coinshot ammo: {coinshot_display}\n"
                f"• Smoker phase: {game.roles.smoker_phase}\n"
                f"• Tineye phase: {game.roles.tineye_phase}\n"
                f"• Game channel: {'Set' if game.channels.game_channel_id else 'Not set'}"
            )
        else:
            await interaction.response.send_message(
                f"✅ **Settings Updated:**\n" + "\n".join(f"• {change}" for change in changes)
            )
    
    @app_commands.command(name="set_pm_roles", description="[GM/IM] Set which roles enable PMs (empty to always allow)")
    @app_commands.describe(
        roles="Comma-separated role names that enable PMs (e.g., 'Messenger,Diplomat'). Leave empty to clear."
    )
    @gm_only()
    @require_game(status='setup')
    async def set_pm_roles(self, interaction: discord.Interaction, roles: str = None):
        """Set roles that keep PMs enabled. When all players with these roles die, PMs are disabled."""
        game = get_game(interaction.guild_id)
        
        if not roles or roles.strip() == "":
            game.roles.pm_enabling_roles = []
            await interaction.response.send_message(
                "✅ PM-enabling roles cleared. PMs will always be available (if enabled)."
            )
            return
        
        # Parse comma-separated roles
        role_list = [r.strip() for r in roles.split(',') if r.strip()]
        game.roles.pm_enabling_roles = role_list
        
        await interaction.response.send_message(
            f"✅ PM-enabling roles set to: **{', '.join(role_list)}**\n"
            f"PMs will be disabled when all players with these roles are eliminated."
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(SetupCog(bot))