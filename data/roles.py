"""
Role definitions and game modes for SEBOT.
Based on Brandon Sanderson's Mistborn magic system.
"""

# Game modes determine which roles are available
GAME_MODES = {
    'all': None,  # None means all roles are available
    'tyrian': [
        'Vanilla',
        'Coinshot',
        'Lurcher', 
        'Rioter',
        'Soother',
        'Smoker',
        'Seeker',
        'Tineye',
        'Thug',
        'Mistborn'
    ]
}

# Comprehensive role definitions
ROLE_DEFINITIONS = {
    'Vanilla': {
        'description': 'No special abilities.',
        'action_phase': None,
        'action_type': None,
        'mafia_equivalent': 'Vanilla',
        'help_text': "You have no special abilities. Your power is your vote and your voice!",
        'commands': []
    },
    'Coinshot': {
        'description': 'Can kill one player at night.',
        'action_phase': 'night',
        'action_type': 'kill',
        'mafia_equivalent': 'Vigilante',
        'help_text': (
            "**Coinshot** (Vigilante)\n"
            "You can kill one player each night.\n\n"
            "**Commands:**\n"
            "• `!coinshot [player]` or `!cs [player]` - Kill target player\n\n"
            "**Notes:**\n"
            "• Can only be used at night\n"
            "• Submit in your GM-PM thread\n"
            "• You can change your target before night ends"
        ),
        'commands': ['!coinshot', '!cs']
    },
    'Lurcher': {
        'description': 'Can protect one player from a single kill at night. Cannot target the same player consecutively.',
        'action_phase': 'night',
        'action_type': 'protect',
        'mafia_equivalent': 'Doctor',
        'help_text': (
            "**Lurcher** (Doctor)\n"
            "You can protect one player from being killed each night.\n\n"
            "**Commands:**\n"
            "• `!lurcher [player]` or `!lurch [player]` - Protect target player\n\n"
            "**Notes:**\n"
            "• Can only be used at night\n"
            "• Cannot protect the same player two nights in a row\n"
            "• Blocks ONE kill (multiple attackers may still succeed)\n"
            "• Submit in your GM-PM thread"
        ),
        'commands': ['!lurcher', '!lurch'],
        'restrictions': ['no_consecutive_target']
    },
    'Rioter': {
        'description': "Can redirect one player's vote to another target during the day. Using this cancels the Rioter's own vote.",
        'action_phase': 'day',
        'action_type': 'redirect_vote',
        'mafia_equivalent': 'Vote Redirector',
        'help_text': (
            "**Rioter** (Vote Redirector)\n"
            "You can force another player's vote to count for a different target.\n\n"
            "**Commands:**\n"
            "• `!riot [player] to [new target]` - Redirect player's vote\n"
            "  Example: `!riot Amber Vulture to Crimson Wolf`\n\n"
            "**Notes:**\n"
            "• Can only be used during the day\n"
            "• Using this ability cancels YOUR vote\n"
            "• Blocked by Smoker protection on the target\n"
            "• Submit in your GM-PM thread"
        ),
        'commands': ['!riot']
    },
    'Soother': {
        'description': "Can cancel one player's vote during the day.",
        'action_phase': 'day',
        'action_type': 'cancel_vote',
        'mafia_equivalent': 'Vote Blocker',
        'help_text': (
            "**Soother** (Vote Blocker)\n"
            "You can cancel another player's vote, making it not count.\n\n"
            "**Commands:**\n"
            "• `!soothe [player]` - Cancel target's vote\n\n"
            "**Notes:**\n"
            "• Can only be used during the day\n"
            "• Blocked by Smoker protection on the target\n"
            "• Submit in your GM-PM thread"
        ),
        'commands': ['!soothe']
    },
    'Smoker': {
        'description': 'Passively protects self from Rioting, Soothing, and Seeking. Can also protect one other player. Can be deactivated.',
        'action_phase': 'passive',
        'action_type': 'role_block_immunity',
        'mafia_equivalent': 'Roleblocker Immunity',
        'help_text': (
            "**Smoker** (Coppercloud)\n"
            "You are passively protected from Rioters, Soothers, and Seekers. "
            "You can also extend this protection to one other player.\n\n"
            "**Commands:**\n"
            "• `!smoke` - View your current Smoker status\n"
            "• `!smoke [player]` - Also protect another player\n"
            "• `!smoke+` - Turn ON your coppercloud (default)\n"
            "• `!smoke-` - Turn OFF your coppercloud\n\n"
            "**Notes:**\n"
            "• Your coppercloud is ON by default at game start\n"
            "• When active, you AND your chosen target are protected\n"
            "• Protected players can't be Rioted, Soothed, or Seeked\n"
            "• Phase restrictions may apply (check with GM)"
        ),
        'commands': ['!smoke', '!smoke+', '!smoke-']
    },
    'Seeker': {
        'description': "Can investigate one player at night to learn their role and/or alignment.",
        'action_phase': 'night',
        'action_type': 'investigate',
        'mafia_equivalent': 'Cop',
        'help_text': (
            "**Seeker** (Cop)\n"
            "You can investigate one player each night to learn about them.\n\n"
            "**Commands:**\n"
            "• `!seek [player]` - Investigate target player\n\n"
            "**Notes:**\n"
            "• Can only be used at night\n"
            "• Results are sent to your GM-PM thread\n"
            "• What you learn depends on GM settings (role, alignment, or both)\n"
            "• Blocked by Smoker protection on the target\n"
            "• Submit in your GM-PM thread"
        ),
        'commands': ['!seek']
    },
    'Tineye': {
        'description': 'Enables PMs for all players while alive. Can submit an anonymous message to be included in the day start announcement.',
        'action_phase': 'night',
        'action_type': 'anonymous_message',
        'mafia_equivalent': 'Messenger/Town Crier',
        'help_text': (
            "**Tineye** (Town Crier)\n"
            "You keep PMs enabled for all players while alive. "
            "You can also submit anonymous messages that appear at day start.\n\n"
            "**Commands:**\n"
            "• `!tin [message]` or `!tinpost [message]` - Submit anonymous message\n"
            "• `!tin` - View your current pending message\n\n"
            "**Notes:**\n"
            "• Maximum 500 characters per message\n"
            "• You can change your message until it's posted\n"
            "• Only ONE message per day (overwrites previous)\n"
            "• Message appears at the start of next day\n"
            "• Phase restrictions may apply (check with GM)"
        ),
        'commands': ['!tin', '!tinpost'],
        'special': ['enables_pms']
    },
    'Thug': {
        'description': 'Survives the first kill or execution targeting them. One-time use.',
        'action_phase': 'passive',
        'action_type': 'survive_kill',
        'mafia_equivalent': 'Bulletproof',
        'help_text': (
            "**Thug** (Bulletproof)\n"
            "You will survive the first attack or execution targeting you.\n\n"
            "**Commands:**\n"
            "• None - this is a passive ability\n\n"
            "**Notes:**\n"
            "• One-time use only\n"
            "• Works against night kills AND day eliminations\n"
            "• After use, you can be killed normally\n"
            "• Delayed death modes may apply (check with GM)"
        ),
        'commands': []
    },
    'Mistborn': {
        'description': 'At the start of each Day, randomly receives one Allomantic power. Cannot receive the same power twice until all have been received.',
        'action_phase': 'special',
        'action_type': 'random_power',
        'mafia_equivalent': 'Jack of All Trades',
        'help_text': (
            "**Mistborn** (Jack of All Trades)\n"
            "At the start of each day, you receive a random Allomantic power.\n\n"
            "**Commands:**\n"
            "• Use `!actions` to see your current power's commands\n"
            "• Commands change based on your current power\n\n"
            "**Power Pool:**\n"
            "Coinshot, Lurcher, Rioter, Soother, Smoker, Seeker, Tineye, Thug\n\n"
            "**Notes:**\n"
            "• You'll be notified of your new power each day\n"
            "• You won't get the same power twice until you've had them all\n"
            "• Your power changes each day"
        ),
        'commands': [],
        'powers_pool': ['Coinshot', 'Lurcher', 'Rioter', 'Soother', 'Smoker', 'Seeker', 'Tineye', 'Thug']
    }
}

# Seeker reveal options (GM configurable)
SEEKER_MODES = {
    'role_only': 'Reveals only the target\'s role',
    'alignment_only': 'Reveals only the target\'s alignment',
    'both': 'Reveals both role and alignment'
}

# Thug protection modes (GM configurable)  
THUG_MODES = {
    'survive': 'Thug survives the attack completely',
    'delayed_phase': 'Thug dies at the start of the next phase',
    'delayed_cycle': 'Thug dies at the start of next cycle'
}

# Action resolution order (lower = resolved first)
RESOLUTION_ORDER = {
    'smoke': 1,
    'protect': 2,
    'survive_kill': 3,
    'kill': 4,
    'investigate': 5,
    'anonymous_message': 6,
    'redirect_vote': 10,
    'cancel_vote': 11
}

# Map action types to roles that can use them
ACTION_TO_ROLES = {
    'kill': ['Coinshot'],
    'protect': ['Lurcher'],
    'redirect_vote': ['Rioter'],
    'cancel_vote': ['Soother'],
    'investigate': ['Seeker'],
    'anonymous_message': ['Tineye'],
}


def get_available_roles(game_mode: str) -> list[str]:
    """Get list of roles available for a game mode."""
    if game_mode == 'all' or game_mode not in GAME_MODES:
        return list(ROLE_DEFINITIONS.keys())
    return GAME_MODES[game_mode]


def get_role_info(role_name: str) -> dict | None:
    """Get role definition by name (case-insensitive)."""
    for name, info in ROLE_DEFINITIONS.items():
        if name.lower() == role_name.lower():
            return info
    return None


def get_role_name_normalized(role_name: str) -> str | None:
    """Get properly-cased role name (case-insensitive lookup)."""
    for name in ROLE_DEFINITIONS.keys():
        if name.lower() == role_name.lower():
            return name
    return None


def is_valid_role(role_name: str, game_mode: str) -> bool:
    """Check if a role is valid for the given game mode (case-insensitive)."""
    available = get_available_roles(game_mode)
    role_lower = role_name.lower()
    return any(r.lower() == role_lower for r in available)


def get_role_help(role_name: str) -> str | None:
    """Get the help text for a role."""
    info = get_role_info(role_name)
    if info:
        return info.get('help_text')
    return None


def get_role_commands(role_name: str) -> list[str]:
    """Get list of commands for a role."""
    info = get_role_info(role_name)
    if info:
        return info.get('commands', [])
    return []