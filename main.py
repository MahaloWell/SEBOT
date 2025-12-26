"""
SEBOT - 17th Shard Elimination Game Bot
Main entry point and message handling.
"""

import discord
from discord.ext import commands
import os
import sys
from dotenv import load_dotenv

# Add the bot directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers.game_state import games, get_game
from helpers.matching import parse_vote_target, parse_kill_target, find_player_by_name
from helpers.anonymous import get_or_create_webhook, announce_vote
from helpers.utils import create_pm_thread
from helpers.role_actions import can_use_role_action, get_current_mistborn_power
from data.identities import ANON_IDENTITIES
from data.roles import ROLE_DEFINITIONS

# Cogs to load
COGS = [
    'cogs.setup',
    'cogs.players',
    'cogs.roles',
    'cogs.gameplay',
    'cogs.admin',
    'cogs.utility'
]


# Load environment
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents)


# ===== BOT EVENTS =====

@bot.event
async def on_ready():
    """Called when the bot connects to Discord."""
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} server(s)')
    
    # Load cogs
    for cog in COGS:
        try:
            await bot.load_extension(cog)
            print(f"Loaded {cog}")
        except Exception as e:
            print(f"Failed to load {cog}: {e}")
    
    # Sync commands
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")


@bot.event
async def on_message(message):
    """Handle text commands and spectator restrictions."""
    if message.author.bot:
        return
    
    # Check spectator restrictions
    for guild_id, game in games.items():
        if game.status == 'active' and message.author.id in game.spectators:
            if message.channel.id != game.dead_spec_thread_id:
                try:
                    await message.delete()
                    await message.author.send(
                        "⚠️ As a spectator, you can only post in the dead/spectator thread. "
                        "Your message was deleted."
                    )
                except:
                    pass
                return
    
    # Route text commands
    content = message.content.lower()
    
    if content.startswith('!say'):
        await handle_say(message)
    elif content.startswith('!pm'):
        await handle_pm(message)
    elif content.startswith('!vote'):
        await handle_vote(message)
    elif content.startswith('!unvote'):
        await handle_unvote(message)
    elif content.startswith('!kill'):
        await handle_kill(message)
    # Role action commands with aliases
    elif content.startswith('!coinshot') or content.startswith('!cs ') or content == '!cs':
        await handle_coinshot(message)
    elif content.startswith('!lurcher') or content.startswith('!lurch'):
        await handle_lurcher(message)
    elif content.startswith('!riot'):
        await handle_riot(message)
    elif content.startswith('!soothe'):
        await handle_soothe(message)
    elif content.startswith('!smoke'):
        await handle_smoke(message)
    elif content.startswith('!seek'):
        await handle_seek(message)
    elif content.startswith('!tinpost') or content.startswith('!tin ') or content == '!tin':
        await handle_tineye(message)
    else:
        await bot.process_commands(message)


# ===== TEXT COMMAND HANDLERS =====

async def handle_say(message):
    """Handle anonymous posting via webhooks."""
    game = get_game(message.guild.id)
    
    if not game:
        await message.channel.send("❌ No game exists in this server!")
        return
    
    if not game.anon_mode:
        await message.channel.send("❌ Anonymous mode is not enabled!")
        return
    
    if game.status != 'active':
        await message.channel.send("❌ Game is not active!")
        return
    
    user_id = message.author.id
    
    if user_id not in game.players:
        await message.channel.send("❌ You are not in this game!")
        return
    
    player = game.players[user_id]
    
    if not player.is_alive:
        await message.channel.send("❌ Dead players cannot post in the main channel!")
        return
    
    if message.channel.id != player.private_channel_id:
        await message.channel.send("❌ Use !say in your private GM-PM thread!")
        return
    
    # Parse message
    parts = message.content.split(maxsplit=1)
    if len(parts) < 2:
        await message.channel.send("❌ Usage: `!say [your message]`")
        return
    
    content = parts[1]
    
    if not player.anon_identity:
        await message.channel.send("❌ You don't have an anonymous identity assigned!")
        return
    
    # Post via webhook
    game_channel = message.guild.get_channel(game.game_channel_id)
    if not game_channel:
        await message.channel.send("❌ Game channel not found!")
        return
    
    webhook = await get_or_create_webhook(game_channel)
    identity_info = ANON_IDENTITIES[player.anon_identity]
    
    embed = discord.Embed(description=content, color=identity_info['color'])
    await webhook.send(
        embed=embed,
        username=player.anon_identity,
        avatar_url=identity_info['avatar_url']
    )
    
    await message.add_reaction("✅")


async def handle_pm(message):
    """Handle private message requests between players."""
    game = get_game(message.guild.id)
    
    if not game:
        await message.channel.send("❌ No game exists in this server!")
        return
    
    if game.status != 'active':
        await message.channel.send("❌ Game is not active!")
        return
    
    user_id = message.author.id
    
    if user_id not in game.players:
        await message.channel.send("❌ You are not in this game!")
        return
    
    player = game.players[user_id]
    
    if not player.is_alive:
        await message.channel.send("❌ Dead players cannot send PMs!")
        return
    
    # Must be in private thread
    if message.channel.id != player.private_channel_id:
        await message.channel.send("❌ Use !pm in your private GM-PM thread!")
        return
    
    # Check if PMs are available
    if not game.are_pms_available():
        await message.channel.send("❌ PMs are currently disabled!")
        return
    
    # Parse target
    parts = message.content.split(maxsplit=1)
    if len(parts) < 2:
        await message.channel.send("❌ Usage: `!pm [player name]`")
        return
    
    target_name = parts[1].strip()
    
    # Find target player
    result = find_player_by_name(game, target_name, alive_only=True)
    
    if not result.success:
        await message.channel.send(result.error)
        return
    
    target_id = result.target_id
    
    # Can't PM yourself
    if target_id == user_id:
        await message.channel.send("❌ You can't PM yourself!")
        return
    
    # Check if PM thread already exists
    existing_thread_id = game.get_pm_thread_id(user_id, target_id)
    if existing_thread_id:
        existing_thread = message.guild.get_thread(existing_thread_id)
        if existing_thread:
            await message.channel.send(
                f"💬 You already have a PM thread with **{result.target_display}**: {existing_thread.mention}"
            )
            return
    
    # Create new PM thread
    pm_thread = await create_pm_thread(message.guild, game, user_id, target_id)
    
    if pm_thread:
        await message.add_reaction("✅")
        await message.channel.send(
            f"💬 Created PM thread with **{result.target_display}**: {pm_thread.mention}"
        )
    else:
        await message.channel.send("❌ Failed to create PM thread. Please contact a GM.")


async def handle_vote(message):
    """Process vote commands."""
    game = get_game(message.guild.id)
    
    if not game:
        await message.channel.send("❌ No game exists in this server!")
        return
    
    if game.status != 'active':
        await message.channel.send("❌ Game is not active!")
        return
    
    if game.phase != 'Day':
        await message.channel.send("❌ Voting only happens during the day phase!")
        return
    
    voter_id = message.author.id
    
    if voter_id not in game.players:
        await message.channel.send("❌ You are not in this game!")
        return
    
    player = game.players[voter_id]
    
    if not player.is_alive:
        await message.channel.send("❌ Dead players cannot vote!")
        return
    
    if game.anon_mode and message.channel.id != player.private_channel_id:
        await message.channel.send("❌ In anonymous mode, use !vote in your private GM-PM thread!")
        return
    
    # Parse target
    parts = message.content.split(maxsplit=1)
    if len(parts) < 2:
        usage = "❌ Usage: `!vote [player name]`"
        if game.allow_no_elimination:
            usage += " or `!vote none`"
        await message.channel.send(usage)
        return
    
    result = parse_vote_target(game, parts[1])
    
    if not result.success:
        await message.channel.send(result.error)
        return
    
    # Record vote
    if game.day_number not in game.votes:
        game.votes[game.day_number] = {}
    
    game.votes[game.day_number][voter_id] = result.target_id
    
    await message.add_reaction("✅")
    await announce_vote(message.guild, game, voter_id, result.target_display)


async def handle_unvote(message):
    """Process unvote commands."""
    game = get_game(message.guild.id)
    
    if not game:
        await message.channel.send("❌ No game exists in this server!")
        return
    
    if game.status != 'active':
        await message.channel.send("❌ Game is not active!")
        return
    
    if game.phase != 'Day':
        await message.channel.send("❌ Voting only happens during the day phase!")
        return
    
    voter_id = message.author.id
    
    if voter_id not in game.players:
        await message.channel.send("❌ You are not in this game!")
        return
    
    player = game.players[voter_id]
    
    if not player.is_alive:
        await message.channel.send("❌ Dead players cannot vote!")
        return
    
    # Check for existing vote
    day_votes = game.get_day_votes()
    if voter_id not in day_votes:
        await message.channel.send("❌ You don't have an active vote to remove!")
        return
    
    # Remove vote
    del game.votes[game.day_number][voter_id]
    
    await message.add_reaction("✅")
    await announce_vote(message.guild, game, voter_id, "", is_unvote=True)


async def handle_kill(message):
    """Process night kill commands."""
    game = get_game(message.guild.id)
    
    if not game:
        await message.channel.send("❌ No game exists in this server!")
        return
    
    if game.status != 'active':
        await message.channel.send("❌ Game is not active!")
        return
    
    if game.phase != 'Night':
        await message.channel.send("❌ Night kills only happen during the night phase!")
        return
    
    killer_id = message.author.id
    
    if killer_id not in game.players:
        await message.channel.send("❌ You are not in this game!")
        return
    
    player = game.players[killer_id]
    
    if not player.is_alive:
        await message.channel.send("❌ Dead players cannot perform actions!")
        return
    
    if player.alignment != 'elims':
        await message.channel.send("❌ You are not an elim!")
        return
    
    # Validate channel
    allowed_channels = [game.elim_discussion_thread_id, player.private_channel_id]
    if message.channel.id not in allowed_channels:
        await message.channel.send(
            "❌ You can only use !kill in the elim discussion thread or your private GM-PM thread!"
        )
        return
    
    # Parse target
    parts = message.content.split(maxsplit=1)
    if len(parts) < 2:
        await message.channel.send("❌ Usage: `!kill [player name]` or `!kill none`")
        return
    
    result = parse_kill_target(game, parts[1])
    
    if not result.success:
        await message.channel.send(result.error)
        return
    
    # Record kill using new action system
    game.add_night_action('elim_kill', killer_id, result.target_id)
    
    await message.add_reaction("✅")
    
    if result.target_id == 'kill_none':
        await message.channel.send("✅ Night kill: **No Kill** (you chose not to kill)")
    else:
        await message.channel.send(f"✅ Night kill submitted for **{result.target_display}**")


# ===== ROLE ACTION HANDLERS =====

async def handle_coinshot(message):
    """Handle Coinshot (Vigilante) night kill."""
    game = get_game(message.guild.id)
    
    if not game:
        await message.channel.send("❌ No game exists in this server!")
        return
    
    if game.status != 'active':
        await message.channel.send("❌ Game is not active!")
        return
    
    user_id = message.author.id
    player = game.players.get(user_id)
    
    if not player:
        await message.channel.send("❌ You are not in this game!")
        return
    
    # Check if player can use this action
    can_use, error = can_use_role_action(game, user_id, 'kill')
    if not can_use:
        await message.channel.send(f"❌ {error}")
        return
    
    # Check ammo limit
    if game.coinshot_ammo > 0:
        kills_used = game.coinshot_kills_used.get(user_id, 0)
        if kills_used >= game.coinshot_ammo:
            await message.channel.send(
                f"❌ You have used all your Coinshot ammunition ({game.coinshot_ammo} kill(s))!"
            )
            return
    
    # Must be in private thread
    if message.channel.id != player.private_channel_id:
        await message.channel.send("❌ Use this command in your private GM-PM thread!")
        return
    
    # Must be night phase
    if 'Night' not in game.phase:
        await message.channel.send("❌ You can only use Coinshot at night!")
        return
    
    # Parse target
    parts = message.content.split(maxsplit=1)
    if len(parts) < 2:
        await message.channel.send("❌ Usage: `!coinshot [player name]`")
        return
    
    result = find_player_by_name(game, parts[1], alive_only=True)
    
    if not result.success:
        await message.channel.send(result.error)
        return
    
    # Can't target self
    if result.target_id == user_id:
        await message.channel.send("❌ You cannot target yourself!")
        return
    
    # Record action
    game.add_night_action('kill', user_id, result.target_id)
    
    # Show ammo status
    ammo_msg = ""
    if game.coinshot_ammo > 0:
        kills_used = game.coinshot_kills_used.get(user_id, 0)
        remaining = game.coinshot_ammo - kills_used - 1  # -1 for this pending kill
        ammo_msg = f"\n*(Ammo remaining after this action: {remaining})*"
    
    await message.add_reaction("✅")
    await message.channel.send(f"🔫 Coinshot target submitted: **{result.target_display}**{ammo_msg}")


async def handle_lurcher(message):
    """Handle Lurcher (Doctor) night protection."""
    game = get_game(message.guild.id)
    
    if not game:
        await message.channel.send("❌ No game exists in this server!")
        return
    
    if game.status != 'active':
        await message.channel.send("❌ Game is not active!")
        return
    
    user_id = message.author.id
    player = game.players.get(user_id)
    
    if not player:
        await message.channel.send("❌ You are not in this game!")
        return
    
    # Check if player can use this action
    can_use, error = can_use_role_action(game, user_id, 'protect')
    if not can_use:
        await message.channel.send(f"❌ {error}")
        return
    
    # Must be in private thread
    if message.channel.id != player.private_channel_id:
        await message.channel.send("❌ Use this command in your private GM-PM thread!")
        return
    
    # Must be night phase
    if 'Night' not in game.phase:
        await message.channel.send("❌ You can only use Lurcher at night!")
        return
    
    # Parse target
    parts = message.content.split(maxsplit=1)
    if len(parts) < 2:
        await message.channel.send("❌ Usage: `!lurcher [player name]`")
        return
    
    result = find_player_by_name(game, parts[1], alive_only=True)
    
    if not result.success:
        await message.channel.send(result.error)
        return
    
    # Check consecutive target restriction
    last_target = game.lurcher_last_targets.get(user_id)
    if last_target == result.target_id:
        await message.channel.send("❌ You cannot protect the same player consecutively!")
        return
    
    # Record action
    game.add_night_action('protect', user_id, result.target_id)
    game.lurcher_last_targets[user_id] = result.target_id
    
    await message.add_reaction("✅")
    await message.channel.send(f"🛡️ Protection target submitted: **{result.target_display}**")


async def handle_riot(message):
    """Handle Rioter vote redirection."""
    game = get_game(message.guild.id)
    
    if not game:
        await message.channel.send("❌ No game exists in this server!")
        return
    
    if game.status != 'active':
        await message.channel.send("❌ Game is not active!")
        return
    
    user_id = message.author.id
    player = game.players.get(user_id)
    
    if not player:
        await message.channel.send("❌ You are not in this game!")
        return
    
    # Check if player can use this action
    can_use, error = can_use_role_action(game, user_id, 'redirect_vote')
    if not can_use:
        await message.channel.send(f"❌ {error}")
        return
    
    # Must be in private thread
    if message.channel.id != player.private_channel_id:
        await message.channel.send("❌ Use this command in your private GM-PM thread!")
        return
    
    # Must be day phase
    if 'Day' not in game.phase:
        await message.channel.send("❌ You can only use Riot during the day!")
        return
    
    # Parse targets: !riot [player1] to [player2]
    content = message.content
    # Remove command prefix (case insensitive)
    if content.lower().startswith('!riot '):
        content = content[6:]
    else:
        await message.channel.send("❌ Usage: `!riot [player] to [new target]`")
        return
    
    # Split on " to " (case insensitive)
    parts = content.lower().split(' to ')
    if len(parts) != 2:
        await message.channel.send("❌ Usage: `!riot [player] to [new target]`\nExample: `!riot Amber Vulture to Crimson Wolf`")
        return
    
    # Get original case from message
    to_index = content.lower().find(' to ')
    target_str = content[:to_index].strip()
    new_target_str = content[to_index + 4:].strip()
    
    result1 = find_player_by_name(game, target_str, alive_only=True)
    if not result1.success:
        await message.channel.send(f"❌ First player: {result1.error}")
        return
    
    result2 = find_player_by_name(game, new_target_str, alive_only=True)
    if not result2.success:
        await message.channel.send(f"❌ Second player: {result2.error}")
        return
    
    # Can't target self
    if result1.target_id == user_id:
        await message.channel.send("❌ You cannot redirect your own vote with Riot!")
        return
    
    # Record action
    game.add_day_action('redirect_vote', user_id, result1.target_id, result2.target_id)
    
    await message.add_reaction("✅")
    await message.channel.send(
        f"😤 Riot submitted: **{result1.target_display}**'s vote will be redirected to **{result2.target_display}**\n"
        f"⚠️ Your own vote will be cancelled."
    )


async def handle_soothe(message):
    """Handle Soother vote cancellation."""
    game = get_game(message.guild.id)
    
    if not game:
        await message.channel.send("❌ No game exists in this server!")
        return
    
    if game.status != 'active':
        await message.channel.send("❌ Game is not active!")
        return
    
    user_id = message.author.id
    player = game.players.get(user_id)
    
    if not player:
        await message.channel.send("❌ You are not in this game!")
        return
    
    # Check if player can use this action
    can_use, error = can_use_role_action(game, user_id, 'cancel_vote')
    if not can_use:
        await message.channel.send(f"❌ {error}")
        return
    
    # Must be in private thread
    if message.channel.id != player.private_channel_id:
        await message.channel.send("❌ Use this command in your private GM-PM thread!")
        return
    
    # Must be day phase
    if 'Day' not in game.phase:
        await message.channel.send("❌ You can only use Soothe during the day!")
        return
    
    # Parse target
    parts = message.content.split(maxsplit=1)
    if len(parts) < 2:
        await message.channel.send("❌ Usage: `!soothe [player name]`")
        return
    
    result = find_player_by_name(game, parts[1], alive_only=True)
    
    if not result.success:
        await message.channel.send(result.error)
        return
    
    # Can't target self
    if result.target_id == user_id:
        await message.channel.send("❌ You cannot Soothe your own vote!")
        return
    
    # Record action
    game.add_day_action('cancel_vote', user_id, result.target_id)
    
    await message.add_reaction("✅")
    await message.channel.send(f"😶 Soothe submitted: **{result.target_display}**'s vote will be cancelled.")


async def handle_smoke(message):
    """Handle Smoker protection toggle."""
    game = get_game(message.guild.id)
    
    if not game:
        await message.channel.send("❌ No game exists in this server!")
        return
    
    if game.status != 'active':
        await message.channel.send("❌ Game is not active!")
        return
    
    user_id = message.author.id
    player = game.players.get(user_id)
    
    if not player:
        await message.channel.send("❌ You are not in this game!")
        return
    
    # Check role (Smoker or Mistborn with Smoker power)
    role = player.role
    if role == 'Mistborn':
        current_power = get_current_mistborn_power(game, user_id)
        if current_power != 'Smoker':
            await message.channel.send("❌ Your current Mistborn power is not Smoker!")
            return
    elif role != 'Smoker':
        await message.channel.send("❌ You are not a Smoker!")
        return
    
    if not player.is_alive:
        await message.channel.send("❌ Dead players cannot use abilities!")
        return
    
    # Must be in private thread
    if message.channel.id != player.private_channel_id:
        await message.channel.send("❌ Use this command in your private GM-PM thread!")
        return
    
    # Check phase restriction
    current_phase = 'Day' if 'Day' in game.phase else 'Night'
    if game.smoker_phase != 'both':
        if game.smoker_phase == 'day' and current_phase != 'Day':
            await message.channel.send("❌ You can only change Smoker settings during the day!")
            return
        if game.smoker_phase == 'night' and current_phase != 'Night':
            await message.channel.send("❌ You can only change Smoker settings during the night!")
            return
    
    # Initialize smoker as active by default
    if user_id not in game.smoker_active:
        game.smoker_active[user_id] = True
    
    # Get the content after !smoke
    content = message.content.strip()
    
    # Check for !smoke+ or !smoke-
    if content.lower() == '!smoke+':
        game.smoker_active[user_id] = True
        await message.add_reaction("✅")
        current_target = game.smoker_targets.get(user_id)
        if current_target:
            target_name = game.get_player_display_name(current_target)
            await message.channel.send(f"🌫️ Smoker activated. You and **{target_name}** are protected.")
        else:
            await message.channel.send("🌫️ Smoker activated. You are protected from Rioting, Soothing, and Seeking.")
        return
    
    if content.lower() == '!smoke-':
        game.smoker_active[user_id] = False
        await message.add_reaction("✅")
        await message.channel.send("🌫️ Smoker deactivated. You and your target are no longer protected.")
        return
    
    # Just !smoke with no arguments - show status
    if content.lower() == '!smoke':
        is_active = game.smoker_active.get(user_id, True)
        current_target = game.smoker_targets.get(user_id)
        target_name = game.get_player_display_name(current_target) if current_target else "No one else"
        
        await message.channel.send(
            f"🌫️ **Smoker Status:**\n"
            f"• Active: {'Yes' if is_active else 'No'}\n"
            f"• Also protecting: {target_name}\n\n"
            f"Commands:\n"
            f"• `!smoke+` - Activate (protect self)\n"
            f"• `!smoke-` - Deactivate (no protection)\n"
            f"• `!smoke [player]` - Also protect another player"
        )
        return
    
    # !smoke [player] - protect another player
    parts = content.split(maxsplit=1)
    if len(parts) < 2:
        await message.channel.send("❌ Usage: `!smoke [player]`, `!smoke+`, or `!smoke-`")
        return
    
    target_str = parts[1].strip()
    
    # Find target player
    result = find_player_by_name(game, target_str, alive_only=True)
    
    if not result.success:
        await message.channel.send(result.error)
        return
    
    # Set protection target (also activates smoker if not already)
    game.smoker_targets[user_id] = result.target_id
    game.smoker_active[user_id] = True
    
    await message.add_reaction("✅")
    await message.channel.send(
        f"🌫️ You are now also protecting **{result.target_display}** from Rioting, Soothing, and Seeking."
    )


async def handle_seek(message):
    """Handle Seeker investigation."""
    game = get_game(message.guild.id)
    
    if not game:
        await message.channel.send("❌ No game exists in this server!")
        return
    
    if game.status != 'active':
        await message.channel.send("❌ Game is not active!")
        return
    
    user_id = message.author.id
    player = game.players.get(user_id)
    
    if not player:
        await message.channel.send("❌ You are not in this game!")
        return
    
    # Check if player can use this action
    can_use, error = can_use_role_action(game, user_id, 'investigate')
    if not can_use:
        await message.channel.send(f"❌ {error}")
        return
    
    # Must be in private thread
    if message.channel.id != player.private_channel_id:
        await message.channel.send("❌ Use this command in your private GM-PM thread!")
        return
    
    # Must be night phase
    if 'Night' not in game.phase:
        await message.channel.send("❌ You can only use Seeker at night!")
        return
    
    # Parse target
    parts = message.content.split(maxsplit=1)
    if len(parts) < 2:
        await message.channel.send("❌ Usage: `!seek [player name]`")
        return
    
    result = find_player_by_name(game, parts[1], alive_only=True)
    
    if not result.success:
        await message.channel.send(result.error)
        return
    
    # Can't target self
    if result.target_id == user_id:
        await message.channel.send("❌ You cannot investigate yourself!")
        return
    
    # Record action
    game.add_night_action('investigate', user_id, result.target_id)
    
    await message.add_reaction("✅")
    await message.channel.send(f"🔍 Investigation target submitted: **{result.target_display}**")


async def handle_tineye(message):
    """Handle Tineye anonymous message."""
    game = get_game(message.guild.id)
    
    if not game:
        await message.channel.send("❌ No game exists in this server!")
        return
    
    if game.status != 'active':
        await message.channel.send("❌ Game is not active!")
        return
    
    user_id = message.author.id
    player = game.players.get(user_id)
    
    if not player:
        await message.channel.send("❌ You are not in this game!")
        return
    
    # Check role (Tineye or Mistborn with Tineye power)
    role = player.role
    if role == 'Mistborn':
        current_power = get_current_mistborn_power(game, user_id)
        if current_power != 'Tineye':
            await message.channel.send("❌ Your current Mistborn power is not Tineye!")
            return
    elif role != 'Tineye':
        await message.channel.send("❌ You are not a Tineye!")
        return
    
    if not player.is_alive:
        await message.channel.send("❌ Dead players cannot use abilities!")
        return
    
    # Must be in private thread
    if message.channel.id != player.private_channel_id:
        await message.channel.send("❌ Use this command in your private GM-PM thread!")
        return
    
    # Check phase restriction
    current_phase = 'Day' if 'Day' in game.phase else 'Night'
    if game.tineye_phase != 'both':
        if game.tineye_phase == 'day' and current_phase != 'Day':
            await message.channel.send("❌ You can only submit Tineye messages during the day!")
            return
        if game.tineye_phase == 'night' and current_phase != 'Night':
            await message.channel.send("❌ You can only submit Tineye messages during the night!")
            return
    
    # Parse message - handle !tin, !tinpost aliases
    content = message.content
    if content.lower().startswith('!tinpost '):
        anon_message = content[9:].strip()
    elif content.lower().startswith('!tin '):
        anon_message = content[5:].strip()
    elif content.lower() == '!tin' or content.lower() == '!tinpost':
        # Show current message
        current_msg = game.tineye_messages.get(user_id)
        if current_msg:
            await message.channel.send(
                f"📜 **Your current Tineye message:**\n*{current_msg}*\n\n"
                f"Use `!tin [new message]` to change it."
            )
        else:
            await message.channel.send(
                f"📜 You haven't submitted a message yet.\n"
                f"Use `!tin [message]` or `!tinpost [message]` to submit one."
            )
        return
    else:
        await message.channel.send("❌ Usage: `!tin [message]` or `!tinpost [message]`")
        return
    
    if len(anon_message) > 500:
        await message.channel.send("❌ Message too long! Maximum 500 characters.")
        return
    
    if not anon_message:
        await message.channel.send("❌ Please provide a message to submit.")
        return
    
    # Check if replacing existing message
    had_previous = user_id in game.tineye_messages
    
    # Store message (one per player, overwrites previous)
    game.tineye_messages[user_id] = anon_message
    
    await message.add_reaction("✅")
    if had_previous:
        await message.channel.send(
            f"📜 Your anonymous message has been **updated**. It will appear at the start of the next day.\n"
            f"Message: *{anon_message}*"
        )
    else:
        await message.channel.send(
            f"📜 Your anonymous message has been recorded. It will appear at the start of the next day.\n"
            f"Message: *{anon_message}*"
        )


# ===== RUN =====

if __name__ == "__main__":
    bot.run(TOKEN)