"""Utility commands - ping, test, command lists."""

import discord
from discord import app_commands
from discord.ext import commands

from helpers.game_state import get_game
from helpers.permissions import is_gm_or_im, gm_only


class UtilityCog(commands.Cog):
    """Utility and help commands."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.command(name="ping", description="Test if the bot is responding")
    async def ping(self, interaction: discord.Interaction):
        """Simple test command."""
        await interaction.response.send_message("Pong! Bot is online and ready.")
    
    @app_commands.command(name="test", description="Test command with GM role check")
    async def test(self, interaction: discord.Interaction):
        """Test if user has GM/IM role."""
        if is_gm_or_im(interaction):
            await interaction.response.send_message("✅ You have GM/IM permissions!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ You don't have GM/IM permissions.", ephemeral=True)
    
    @app_commands.command(name="commands", description="Show available command categories")
    async def commands_overview(self, interaction: discord.Interaction):
        """Show overview of command categories."""
        is_gm = is_gm_or_im(interaction)
        
        response = """**📚 SEBOT Command Categories**

Use these commands to see detailed command lists:

• `/player_commands` - Gameplay commands (voting, actions, etc.)
• `/pregame_commands` - Pre-game commands (join, leave, roles)"""
        
        if is_gm:
            response += "\n• `/gm_commands` - GM/IM setup and management commands"
        
        response += """

**🔧 Utility:**
• `/ping` - Test if bot is responding
• `/test` - Test your permissions"""
        
        await interaction.response.send_message(response, ephemeral=True)
    
    @app_commands.command(name="gm_commands", description="[GM/IM] Show GM/IM command list")
    @gm_only()
    async def gm_commands(self, interaction: discord.Interaction):
        """Display GM/IM commands."""
        response = """**🎮 GM/IM Setup Commands**

**Game Creation:**
• `/create_game` - Create a new game
• `/set_game_name` - Set game tag and flavor name
• `/create_game_channel` - Create game discussion channel
• `/set_game_channel` - Use existing channel as game channel

**Configuration:**
• `/config_game` - Configure game settings (timing, win condition, anon mode, faction names, role settings)
• `/set_pm_roles` - Set which roles enable PMs

**Role Management:**
• `/assign_gm` / `/assign_im` - Give GM/IM roles
• `/remove_gm` / `/remove_im` - Remove GM/IM roles

**Player Setup:**
• `/assign_role` - Assign alignment and role to a player
• `/randomize_alignments` - Randomly assign village/elim alignments
• `/assign_identities` - Randomly assign anonymous identities
• `/assign_identity` - Manually assign specific anonymous identity
• `/remove_player` - Remove a player (before game starts)

**Game Control:**
• `/start_game` - Start the game
• `/end_phase` - Manually end current phase
• `/end_game` - End and archive the game

**Moderation:**
• `/clear_votes` - Clear all votes for current day
• `/force_kill` - Force eliminate a player
• `/revive` - Revive an eliminated player
• `/player_list` - View all players with alignments/roles (GM view)"""
        
        await interaction.response.send_message(response, ephemeral=True)
    
    @app_commands.command(name="pregame_commands", description="Show pre-game command list")
    async def pregame_commands(self, interaction: discord.Interaction):
        """Display pre-game commands."""
        game = get_game(interaction.guild_id)
        
        response = """**📋 Pre-Game Commands**

**Joining:**
• `/join_game` - Join the current game
• `/leave_game` - Leave before game starts
• `/spectate_game` - Spectate the active game

**Information:**
• `/player_list` - View all players
• `/roles` - View available roles for this game mode"""
        
        if game:
            response += f"\n\n**Current Game Status:** {game.status.title()}"
            response += f"\n**Players:** {len(game.players)}"
            if game.config.anon_mode:
                response += "\n**Mode:** Anonymous"
        else:
            response += "\n\n*No game currently exists in this server.*"
        
        await interaction.response.send_message(response, ephemeral=True)
    
    @app_commands.command(name="player_commands", description="Show gameplay command list")
    async def player_commands(self, interaction: discord.Interaction):
        """Display player gameplay commands."""
        game = get_game(interaction.guild_id)
        
        response = """**👤 Player Gameplay Commands**

**Slash Commands:**
• `/vote_count` - See current vote tallies
• `/all_vote_counts` - See all vote results from this game
• `/time_remaining` - Check phase time
• `/player_list` - View all players

**Voting (in game channel"""
        
        # Describe where voting happens
        if game and game.config.secret_votes:
            response += " or GM-PM thread - most recent counts):"
        elif game and game.config.anon_mode:
            response += " via GM-PM thread in anon mode):"
        else:
            response += "):"
        
        response += "\n• `!vote [player]` - Vote for a player during day"
        
        if game and game.config.allow_no_elimination:
            response += " (or `!vote none`)"
        
        response += """
• `!unvote` - Remove your current vote

**Text Commands (use in your GM-PM thread):**
• `!actions` - View your role's abilities and commands"""
        
        if not game or game.config.pms_enabled:
            response += "\n• `!pm [player]` - Start a private conversation"
        
        if not game or game.config.anon_mode:
            response += "\n• `!say [message]` - Post anonymously in game channel"
        
        # Check if user is elim
        if game and interaction.user.id in game.players:
            if game.players[interaction.user.id].alignment == 'elims':
                response += f"\n• `!kill [player]` or `!kill none` - {game.config.elim_name} night kill"
        
        response += """

**⚔️ Role Action Commands (use in GM-PM thread):**
• `!coinshot [player]` / `!cs [player]` - Coinshot kill (night)
• `!lurcher [player]` / `!lurch [player]` - Lurcher protect (night)
• `!seek [player]` - Seeker investigate (night)
• `!riot [player] to [target]` - Rioter redirect vote (day)
• `!soothe [player]` - Soother cancel vote (day)
• `!smoke [player]` / `!smoke+` / `!smoke-` - Smoker protection
• `!tin [message]` / `!tinpost [message]` - Tineye anonymous message

*Use `!actions` in your GM-PM thread to see only YOUR role's commands.*"""
        
        await interaction.response.send_message(response, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(UtilityCog(bot))