"""
Messaging handlers for !say and !pm commands.
"""

import discord

from helpers.game_state import get_game
from helpers.matching import find_player_by_name
from helpers.anonymous import get_or_create_webhook
from helpers.utils import create_pm_thread
from data.identities import ANON_IDENTITIES
from messages import Errors, Usage


async def handle_say(message):
    """Handle anonymous posting via webhooks."""
    game = get_game(message.guild.id)
    
    if not game:
        await message.channel.send(Errors.NO_GAME)
        return
    
    if not game.config.anon_mode:
        await message.channel.send(Errors.ANON_NOT_ENABLED)
        return
    
    if game.status != 'active':
        await message.channel.send(Errors.GAME_NOT_ACTIVE)
        return
    
    user_id = message.author.id
    
    if user_id not in game.players:
        await message.channel.send(Errors.NOT_IN_GAME)
        return
    
    player = game.players[user_id]
    
    if not player.is_alive:
        await message.channel.send("❌ Dead players cannot post in the main channel!")
        return
    
    if message.channel.id != player.private_channel_id:
        await message.channel.send(Errors.SAY_IN_PM_ONLY)
        return
    
    # Parse message
    parts = message.content.split(maxsplit=1)
    if len(parts) < 2:
        await message.channel.send(Errors.usage(Usage.SAY))
        return
    
    content = parts[1]
    
    if not player.anon_identity:
        await message.channel.send("❌ You don't have an anonymous identity assigned!")
        return
    
    # Post via webhook
    game_channel = message.guild.get_channel(game.channels.game_channel_id)
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
        await message.channel.send(Errors.NO_GAME)
        return
    
    if game.status != 'active':
        await message.channel.send(Errors.GAME_NOT_ACTIVE)
        return
    
    user_id = message.author.id
    
    if user_id not in game.players:
        await message.channel.send(Errors.NOT_IN_GAME)
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
        await message.channel.send(Errors.PMS_DISABLED)
        return
    
    # Parse target
    parts = message.content.split(maxsplit=1)
    if len(parts) < 2:
        await message.channel.send(Errors.usage(Usage.PM))
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
        await message.channel.send(Errors.PM_SELF)
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