"""
Voting handlers for !vote and !unvote commands.
"""

from helpers.game_state import get_game
from helpers.matching import parse_vote_target
from helpers.anonymous import announce_vote
from messages import Errors


async def handle_vote(message):
    """Process vote commands."""
    game = get_game(message.guild.id)
    
    if not game:
        await message.channel.send(Errors.NO_GAME)
        return
    
    if game.status != 'active':
        await message.channel.send(Errors.GAME_NOT_ACTIVE)
        return
    
    if not game.is_day():
        await message.channel.send("❌ Voting only happens during the day phase!")
        return
    
    voter_id = message.author.id
    
    if voter_id not in game.players:
        await message.channel.send(Errors.NOT_IN_GAME)
        return
    
    player = game.players[voter_id]
    
    if not player.is_alive:
        await message.channel.send("❌ Dead players cannot vote!")
        return
    
    # Determine if this is a private (secret) vote
    is_private_vote = message.channel.id == player.private_channel_id
    
    # Check vote location rules
    if game.config.anon_mode:
        # Anon mode: MUST vote in GM-PM thread
        if not is_private_vote:
            await message.channel.send("❌ In anonymous mode, use !vote in your private GM-PM thread!")
            return
    elif game.config.secret_votes:
        # Secret votes: can vote in either place (game channel or GM-PM)
        pass  # Allow both locations
    else:
        # Normal mode: should vote in game channel (but we don't enforce it strictly)
        pass
    
    # Parse target
    parts = message.content.split(maxsplit=1)
    if len(parts) < 2:
        usage = "❌ Usage: `!vote [player name]`"
        if game.config.allow_no_elimination:
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
    
    # Announce vote (or not, depending on mode and location)
    if game.config.secret_votes and is_private_vote:
        # Secret vote from GM-PM thread - don't announce publicly
        await message.channel.send(f"🗳️ Secret vote recorded for **{result.target_display}**")
    else:
        # Normal announcement (handles anon mode internally)
        await announce_vote(message.guild, game, voter_id, result.target_display)


async def handle_unvote(message):
    """Process unvote commands."""
    game = get_game(message.guild.id)
    
    if not game:
        await message.channel.send(Errors.NO_GAME)
        return
    
    if game.status != 'active':
        await message.channel.send(Errors.GAME_NOT_ACTIVE)
        return
    
    if not game.is_day():
        await message.channel.send("❌ Voting only happens during the day phase!")
        return
    
    voter_id = message.author.id
    
    if voter_id not in game.players:
        await message.channel.send(Errors.NOT_IN_GAME)
        return
    
    player = game.players[voter_id]
    
    if not player.is_alive:
        await message.channel.send("❌ Dead players cannot vote!")
        return
    
    # Determine if this is a private (secret) unvote
    is_private_vote = message.channel.id == player.private_channel_id
    
    # Check vote location rules (same as vote)
    if game.config.anon_mode and not is_private_vote:
        await message.channel.send("❌ In anonymous mode, use !unvote in your private GM-PM thread!")
        return
    
    # Check for existing vote
    day_votes = game.get_day_votes()
    if voter_id not in day_votes:
        await message.channel.send(Errors.NO_VOTE_TO_REMOVE)
        return
    
    # Remove vote
    del game.votes[game.day_number][voter_id]
    
    await message.add_reaction("✅")
    
    # Announce unvote (or not, depending on mode and location)
    if game.config.secret_votes and is_private_vote:
        # Secret unvote from GM-PM thread - don't announce publicly
        await message.channel.send("↩️ Secret vote removed")
    else:
        # Normal announcement
        await announce_vote(message.guild, game, voter_id, "", is_unvote=True)