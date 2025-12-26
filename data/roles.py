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

# Role definitions with mechanics
# action_phase: 'day', 'night', 'passive', or None
# action_type: describes what the action does
ROLE_DEFINITIONS = {
    'Vanilla': {
        'description': 'No special abilities.',
        'action_phase': None,
        'action_type': None,
        'mafia_equivalent': 'Vanilla'
    },
    'Coinshot': {
        'description': 'Can kill one player at night.',
        'action_phase': 'night',
        'action_type': 'kill',
        'command': '!coinshot [player]',
        'mafia_equivalent': 'Vigilante'
    },
    'Lurcher': {
        'description': 'Can protect one player from a single kill at night. Cannot target the same player consecutively.',
        'action_phase': 'night',
        'action_type': 'protect',
        'command': '!lurcher [player]',
        'restrictions': ['no_consecutive_target'],
        'mafia_equivalent': 'Doctor'
    },
    'Rioter': {
        'description': 'Can redirect one player\'s vote to another target during the day. Using this cancels the Rioter\'s own vote.',
        'action_phase': 'day',
        'action_type': 'redirect_vote',
        'command': '!riot [player] [new target]',
        'mafia_equivalent': 'Vote Redirector'
    },
    'Soother': {
        'description': 'Can cancel one player\'s vote during the day.',
        'action_phase': 'day',
        'action_type': 'cancel_vote',
        'command': '!soothe [player]',
        'mafia_equivalent': 'Vote Blocker'
    },
    'Smoker': {
        'description': 'Passively protects self from Rioting, Soothing, and Seeking. Can also protect one other player. Can be deactivated.',
        'action_phase': 'passive',
        'action_type': 'role_block_immunity',
        'command': '!smoke [player] or !smoke off',
        'mafia_equivalent': 'Roleblocker Immunity'
    },
    'Seeker': {
        'description': 'Can investigate one player at night to learn their role and/or alignment.',
        'action_phase': 'night',
        'action_type': 'investigate',
        'command': '!seek [player]',
        'mafia_equivalent': 'Cop'
    },
    'Tineye': {
        'description': 'Enables PMs for all players while alive. Can submit an anonymous message to be included in the day start announcement.',
        'action_phase': 'night',
        'action_type': 'anonymous_message',
        'command': '!tineye [message]',
        'special': ['enables_pms'],
        'mafia_equivalent': 'Messenger/Town Crier'
    },
    'Thug': {
        'description': 'Survives the first kill or execution targeting them. One-time use.',
        'action_phase': 'passive',
        'action_type': 'survive_kill',
        'mafia_equivalent': 'Bulletproof/Commuter'
    },
    'Mistborn': {
        'description': 'At the start of each Day, randomly receives one Allomantic power. Cannot receive the same power twice until all have been received.',
        'action_phase': 'special',
        'action_type': 'random_power',
        'powers_pool': ['Coinshot', 'Lurcher', 'Rioter', 'Soother', 'Smoker', 'Seeker', 'Tineye', 'Thug'],
        'mafia_equivalent': 'Jack of All Trades'
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
    'delayed_phase': 'Thug dies at the end of the current phase',
    'delayed_cycle': 'Thug dies at the end of the next full day/night cycle'
}

# Action resolution order
# Lower number = resolved first
RESOLUTION_ORDER = {
    'smoke': 1,          # Smoker protection applied first
    'protect': 2,        # Lurcher protection
    'survive_kill': 3,   # Thug passive
    'kill': 4,           # Coinshot/Elim kills
    'investigate': 5,    # Seeker
    'anonymous_message': 6,  # Tineye messages collected
    'redirect_vote': 10,     # Rioter (day action)
    'cancel_vote': 11        # Soother (day action)
}


def get_available_roles(game_mode: str) -> list[str]:
    """Get list of roles available for a game mode."""
    if game_mode == 'all' or game_mode not in GAME_MODES:
        return list(ROLE_DEFINITIONS.keys())
    return GAME_MODES[game_mode]


def get_role_info(role_name: str) -> dict | None:
    """Get role definition by name."""
    return ROLE_DEFINITIONS.get(role_name)


def is_valid_role(role_name: str, game_mode: str) -> bool:
    """Check if a role is valid for the given game mode."""
    available = get_available_roles(game_mode)
    return role_name in available


def get_role_command(role_name: str) -> str | None:
    """Get the command for a role's action."""
    role = ROLE_DEFINITIONS.get(role_name)
    if role:
        return role.get('command')
    return None