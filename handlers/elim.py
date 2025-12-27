"""
Elim (Mafia) action handlers for !kill command.
"""

from helpers.game_state import get_game
from helpers.matching import parse_kill_target
from messages import Errors, Success, Usage


async def handle_kill(message):
    """Process night kill commands from elims."""
    game = get_game(message.guild.id)
    
    if not game:
        await message.channel.send(Errors.NO_GAME)
        return
    
    if game.status != 'active':
        await message.channel.send(Errors.GAME_NOT_ACTIVE)
        return
    
    if not game.is_night():
        await message.channel.send("❌ Night kills only happen during the night phase!")
        return
    
    killer_id = message.author.id
    
    if killer_id not in game.players:
        await message.channel.send(Errors.NOT_IN_GAME)
        return
    
    player = game.players[killer_id]
    
    if not player.is_alive:
        await message.channel.send(Errors.DEAD_PLAYER)
        return
    
    if player.alignment != 'elims':
        await message.channel.send("❌ You are not an elim!")
        return
    
    # Validate channel
    allowed_channels = [game.channels.elim_discussion_thread_id, player.private_channel_id]
    if message.channel.id not in allowed_channels:
        await message.channel.send(
            "❌ You can only use !kill in the elim discussion thread or your private GM-PM thread!"
        )
        return
    
    # Parse target
    parts = message.content.split(maxsplit=1)
    if len(parts) < 2:
        await message.channel.send(Errors.usage(Usage.KILL))
        return
    
    result = parse_kill_target(game, parts[1])
    
    if not result.success:
        await message.channel.send(result.error)
        return
    
    # Record kill using action system
    game.add_night_action('elim_kill', killer_id, result.target_id)
    
    await message.add_reaction("✅")
    
    if result.target_id == 'kill_none':
        await message.channel.send(Success.kill_none())
    else:
        await message.channel.send(Success.kill_submitted(result.target_display))