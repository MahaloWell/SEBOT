"""
SEBOT - 17th Shard Elimination Game Bot
Main entry point and message routing.
"""

import discord
from discord.ext import commands
import os
import sys
from dotenv import load_dotenv

# Add the bot directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers.game_state import games
from handlers import (
    handle_say, handle_pm,
    handle_vote, handle_unvote,
    handle_kill,
    handle_coinshot, handle_lurcher, handle_riot, handle_soothe,
    handle_smoke, handle_seek, handle_tineye, handle_actions
)

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
            if message.channel.id != game.channels.dead_spec_thread_id:
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
    
    # Messaging commands
    if content.startswith('!say'):
        await handle_say(message)
    elif content.startswith('!pm'):
        await handle_pm(message)
    
    # Voting commands
    elif content.startswith('!vote'):
        await handle_vote(message)
    elif content.startswith('!unvote'):
        await handle_unvote(message)
    
    # Elim kill command
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
    
    # Help command
    elif content.startswith('!actions') or content == '!action' or content == '!help':
        await handle_actions(message)
    
    # Pass to discord.py command processing
    else:
        await bot.process_commands(message)


# ===== RUN =====

if __name__ == "__main__":
    bot.run(TOKEN)