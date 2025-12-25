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
from data.identities import ANON_IDENTITIES

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
    
    # Record kill
    if game.day_number not in game.night_actions:
        game.night_actions[game.day_number] = {}
    
    game.night_actions[game.day_number]['elim_kill'] = result.target_id
    
    await message.add_reaction("✅")
    
    if result.target_id == 'kill_none':
        await message.channel.send("✅ Night kill: **No Kill** (you chose not to kill)")
    else:
        await message.channel.send(f"✅ Night kill submitted for **{result.target_display}**")


# ===== RUN =====

if __name__ == "__main__":
    bot.run(TOKEN)