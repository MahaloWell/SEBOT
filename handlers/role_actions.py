"""
Role action handlers for Tyrian roles.
Coinshot, Lurcher, Rioter, Soother, Smoker, Seeker, Tineye, etc.
"""

from helpers.game_state import get_game
from helpers.matching import find_player_by_name
from helpers.role_actions import can_use_role_action, get_current_mistborn_power
from data.roles import get_role_help
from messages import Errors, Success, Info, Usage


# ===== VALIDATION HELPERS =====

async def validate_role_action(message, action_type: str, required_phase: str = None) -> tuple:
    """
    Validate a role action command. Checks private thread FIRST to avoid leaking role info.
    Returns (game, player, user_id) if valid, or (None, None, None) if invalid.
    
    IMPORTANT: Checks private thread before anything else to prevent role revelation.
    """
    game = get_game(message.guild.id)
    user_id = message.author.id
    
    # Check game exists and is active (silent fail - no game context)
    if not game or game.status != 'active':
        return None, None, None
    
    player = game.players.get(user_id)
    if not player:
        return None, None, None  # Silent fail - not in game
    
    # CRITICAL: Check private thread FIRST before revealing any role-specific info
    if message.channel.id != player.private_channel_id:
        await message.channel.send(Errors.WRONG_CHANNEL)
        return None, None, None
    
    # Now we're in private thread, safe to give specific feedback
    if not player.is_alive:
        await message.channel.send(Errors.DEAD_PLAYER)
        return None, None, None
    
    # Check role permission
    can_use, error = can_use_role_action(game, user_id, action_type)
    if not can_use:
        await message.channel.send(f"❌ {error}")
        return None, None, None
    
    # Check phase if required
    if required_phase:
        if required_phase == 'night' and not game.is_night():
            await message.channel.send(Errors.NIGHT_ONLY)
            return None, None, None
        elif required_phase == 'day' and not game.is_day():
            await message.channel.send(Errors.DAY_ONLY)
            return None, None, None
    
    return game, player, user_id


def parse_action_target(message, command_prefix: str) -> str | None:
    """Extract target string from a command message."""
    content = message.content
    # Handle various command prefixes
    for prefix in command_prefix.split('|'):
        if content.lower().startswith(prefix.lower()):
            return content[len(prefix):].strip()
    return None


# ===== ROLE ACTION HANDLERS =====

async def handle_coinshot(message):
    """Handle Coinshot (Vigilante) night kill."""
    game, player, user_id = await validate_role_action(message, 'kill', 'night')
    if not game:
        return
    
    # Check ammo limit
    if game.roles.coinshot_ammo > 0:
        kills_used = game.coinshot_kills_used.get(user_id, 0)
        if kills_used >= game.roles.coinshot_ammo:
            await message.channel.send(
                Errors.COINSHOT_NO_AMMO.format(ammo=game.roles.coinshot_ammo)
            )
            return
    
    # Parse target
    target_str = parse_action_target(message, '!coinshot |!cs ')
    if not target_str:
        await message.channel.send(Errors.usage(Usage.COINSHOT))
        return
    
    result = find_player_by_name(game, target_str, alive_only=True)
    if not result.success:
        await message.channel.send(result.error)
        return
    
    if result.target_id == user_id:
        await message.channel.send(Errors.NO_SELF_TARGET)
        return
    
    # Record action (replaces any existing)
    game.add_night_action('kill', user_id, result.target_id)
    
    ammo_remaining = None
    if game.roles.coinshot_ammo > 0:
        kills_used = game.coinshot_kills_used.get(user_id, 0)
        ammo_remaining = game.roles.coinshot_ammo - kills_used - 1
    
    await message.add_reaction("✅")
    await message.channel.send(Success.coinshot(result.target_display, ammo_remaining))


async def handle_lurcher(message):
    """Handle Lurcher (Doctor) night protection."""
    game, player, user_id = await validate_role_action(message, 'protect', 'night')
    if not game:
        return
    
    # Parse target
    target_str = parse_action_target(message, '!lurcher |!lurch ')
    if not target_str:
        await message.channel.send(Errors.usage(Usage.LURCHER))
        return
    
    result = find_player_by_name(game, target_str, alive_only=True)
    if not result.success:
        await message.channel.send(result.error)
        return
    
    # Check consecutive target restriction
    last_target = game.lurcher_last_targets.get(user_id)
    if last_target == result.target_id:
        await message.channel.send(Errors.LURCHER_CONSECUTIVE)
        return
    
    # Record action (replaces any existing)
    game.add_night_action('protect', user_id, result.target_id)
    game.lurcher_last_targets[user_id] = result.target_id
    
    await message.add_reaction("✅")
    await message.channel.send(Success.lurcher(result.target_display))


async def handle_riot(message):
    """Handle Rioter vote redirection."""
    game, player, user_id = await validate_role_action(message, 'redirect_vote', 'day')
    if not game:
        return
    
    # Parse targets: !riot [player1] to [player2]
    content = message.content
    if content.lower().startswith('!riot '):
        content = content[6:]
    else:
        await message.channel.send(Errors.usage(Usage.RIOT, Usage.RIOT_EXAMPLE))
        return
    
    # Split on " to " (case insensitive)
    to_index = content.lower().find(' to ')
    if to_index == -1:
        await message.channel.send(Errors.usage(Usage.RIOT, Usage.RIOT_EXAMPLE))
        return
    
    target_str = content[:to_index].strip()
    new_target_str = content[to_index + 4:].strip()
    
    if not target_str or not new_target_str:
        await message.channel.send(Errors.usage(Usage.RIOT))
        return
    
    result1 = find_player_by_name(game, target_str, alive_only=True)
    if not result1.success:
        await message.channel.send(f"❌ First player: {result1.error}")
        return
    
    result2 = find_player_by_name(game, new_target_str, alive_only=True)
    if not result2.success:
        await message.channel.send(f"❌ Second player: {result2.error}")
        return
    
    if result1.target_id == user_id:
        await message.channel.send(Errors.RIOT_SELF_VOTE)
        return
    
    # Record action (replaces any existing)
    game.add_day_action('redirect_vote', user_id, result1.target_id, result2.target_id)
    
    await message.add_reaction("✅")
    await message.channel.send(Success.riot(result1.target_display, result2.target_display))


async def handle_soothe(message):
    """Handle Soother vote cancellation."""
    game, player, user_id = await validate_role_action(message, 'cancel_vote', 'day')
    if not game:
        return
    
    # Parse target
    target_str = parse_action_target(message, '!soothe ')
    if not target_str:
        await message.channel.send(Errors.usage(Usage.SOOTHE))
        return
    
    result = find_player_by_name(game, target_str, alive_only=True)
    if not result.success:
        await message.channel.send(result.error)
        return
    
    if result.target_id == user_id:
        await message.channel.send(Errors.SOOTHE_SELF)
        return
    
    # Record action (replaces any existing)
    game.add_day_action('cancel_vote', user_id, result.target_id)
    
    await message.add_reaction("✅")
    await message.channel.send(Success.soothe(result.target_display))


async def handle_smoke(message):
    """Handle Smoker protection toggle."""
    game = get_game(message.guild.id)
    user_id = message.author.id
    
    # Silent fail for basic checks
    if not game or game.status != 'active':
        return
    
    player = game.players.get(user_id)
    if not player:
        return
    
    # CRITICAL: Check private thread FIRST before revealing any role info
    if message.channel.id != player.private_channel_id:
        await message.channel.send(Errors.WRONG_CHANNEL)
        return
    
    # Now safe to give role-specific feedback
    if not player.is_alive:
        await message.channel.send(Errors.DEAD_PLAYER)
        return
    
    # Check role (Smoker or Mistborn with Smoker power)
    role = player.role
    if role == 'Mistborn':
        current_power = get_current_mistborn_power(game, user_id)
        if current_power != 'Smoker':
            await message.channel.send(Errors.MISTBORN_WRONG_POWER.format(power='Smoker'))
            return
    elif role != 'Smoker':
        await message.channel.send("❌ You are not a Smoker!")
        return
    
    # Check phase restriction
    if not game.is_allowed_phase(game.roles.smoker_phase):
        phase_name = game.roles.smoker_phase.capitalize()
        await message.channel.send(f"❌ You can only change Smoker settings during {phase_name}!")
        return
    
    # Initialize smoker as active by default
    if user_id not in game.smoker_active:
        game.smoker_active[user_id] = True
    
    content = message.content.strip()
    
    # Check for !smoke+ or !smoke-
    if content.lower() == '!smoke+':
        game.smoker_active[user_id] = True
        await message.add_reaction("✅")
        current_target = game.smoker_targets.get(user_id)
        if current_target:
            target_name = game.get_player_display_name(current_target)
            await message.channel.send(Success.smoke_activated(target_name))
        else:
            await message.channel.send(Success.smoke_activated())
        return
    
    if content.lower() == '!smoke-':
        game.smoker_active[user_id] = False
        await message.add_reaction("✅")
        await message.channel.send(Success.smoke_deactivated())
        return
    
    # Just !smoke with no arguments - show status
    if content.lower() == '!smoke':
        is_active = game.smoker_active.get(user_id, True)
        current_target = game.smoker_targets.get(user_id)
        target_name = game.get_player_display_name(current_target) if current_target else None
        await message.channel.send(Info.smoker_status(is_active, target_name))
        return
    
    # !smoke [player] - protect another player
    target_str = parse_action_target(message, '!smoke ')
    if not target_str:
        await message.channel.send(Errors.usage(Usage.SMOKE))
        return
    
    result = find_player_by_name(game, target_str, alive_only=True)
    if not result.success:
        await message.channel.send(result.error)
        return
    
    game.smoker_targets[user_id] = result.target_id
    game.smoker_active[user_id] = True
    
    await message.add_reaction("✅")
    await message.channel.send(Success.smoke_target(result.target_display))


async def handle_seek(message):
    """Handle Seeker investigation."""
    game, player, user_id = await validate_role_action(message, 'investigate', 'night')
    if not game:
        return
    
    # Parse target
    target_str = parse_action_target(message, '!seek ')
    if not target_str:
        await message.channel.send(Errors.usage(Usage.SEEK))
        return
    
    result = find_player_by_name(game, target_str, alive_only=True)
    if not result.success:
        await message.channel.send(result.error)
        return
    
    if result.target_id == user_id:
        await message.channel.send("❌ You cannot investigate yourself!")
        return
    
    # Record action (replaces any existing)
    game.add_night_action('investigate', user_id, result.target_id)
    
    await message.add_reaction("✅")
    await message.channel.send(Success.seek(result.target_display))


async def handle_tineye(message):
    """Handle Tineye anonymous message."""
    game = get_game(message.guild.id)
    user_id = message.author.id
    
    # Silent fail for basic checks
    if not game or game.status != 'active':
        return
    
    player = game.players.get(user_id)
    if not player:
        return
    
    # CRITICAL: Check private thread FIRST before revealing any role info
    if message.channel.id != player.private_channel_id:
        await message.channel.send(Errors.WRONG_CHANNEL)
        return
    
    # Now safe to give role-specific feedback
    if not player.is_alive:
        await message.channel.send(Errors.DEAD_PLAYER)
        return
    
    # Check role (Tineye or Mistborn with Tineye power)
    role = player.role
    if role == 'Mistborn':
        current_power = get_current_mistborn_power(game, user_id)
        if current_power != 'Tineye':
            await message.channel.send(Errors.MISTBORN_WRONG_POWER.format(power='Tineye'))
            return
    elif role != 'Tineye':
        await message.channel.send("❌ You are not a Tineye!")
        return
    
    # Check phase restriction
    if not game.is_allowed_phase(game.roles.tineye_phase):
        phase_name = game.roles.tineye_phase.capitalize()
        await message.channel.send(f"❌ You can only submit Tineye messages during {phase_name}!")
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
            await message.channel.send(Info.tineye_current(current_msg))
        else:
            await message.channel.send(Info.tineye_none())
        return
    else:
        await message.channel.send(Errors.usage(Usage.TINEYE))
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
    await message.channel.send(Success.tineye_submitted(anon_message, had_previous))


async def handle_actions(message):
    """Show the player their available actions based on their role."""
    game = get_game(message.guild.id)
    user_id = message.author.id
    
    if not game:
        await message.channel.send(Errors.NO_GAME)
        return
    
    if game.status != 'active':
        await message.channel.send(Errors.GAME_NOT_ACTIVE)
        return
    
    player = game.players.get(user_id)
    if not player:
        await message.channel.send(Errors.NOT_IN_GAME)
        return
    
    # Must be in private thread to see role info
    if message.channel.id != player.private_channel_id:
        await message.channel.send(Errors.ACTIONS_IN_PM)
        return
    
    role = player.role or 'Vanilla'
    
    # For Mistborn, show current power's help
    if role == 'Mistborn':
        current_power = get_current_mistborn_power(game, user_id)
        
        # Get base Mistborn help
        mistborn_help = get_role_help('Mistborn')
        
        if current_power:
            power_help = get_role_help(current_power)
            await message.channel.send(
                f"{mistborn_help}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"**Your Current Power: {current_power}**\n\n"
                f"{power_help}"
            )
        else:
            await message.channel.send(
                f"{mistborn_help}\n\n"
                f"*You haven't been assigned a power yet. "
                f"You'll receive one at the start of each day.*"
            )
    else:
        # Regular role
        help_text = get_role_help(role)
        if help_text:
            await message.channel.send(help_text)
        else:
            await message.channel.send(f"No help available for role: {role}")