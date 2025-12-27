"""Game state management and data structures."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from data.identities import ANON_IDENTITIES


# Global games storage (indexed by guild_id)
games: dict[int, 'Game'] = {}


@dataclass
class Player:
    """Represents a player in the game."""
    user_id: int
    username: str
    display_name: str
    anon_identity: Optional[str] = None
    private_channel_id: Optional[int] = None
    alignment: Optional[str] = None  # 'village' or 'elims'
    role: Optional[str] = None
    is_alive: bool = True
    character_name: Optional[str] = None


@dataclass
class GameConfig:
    """General game settings - set at creation, rarely change during play."""
    anon_mode: bool = False
    secret_votes: bool = False              # Allow voting in GM-PM thread (most recent counts)
    day_length_minutes: int = 2880          # 48 hours
    night_length_minutes: int = 1440        # 24 hours
    win_condition: str = 'parity'           # 'parity', 'overparity', 'last_man_standing'
    auto_phase_transition: bool = True
    allow_no_elimination: bool = True
    min_votes_to_eliminate: int = 0         # 0=plurality, -1=force RNG if 0 votes
    pms_enabled: bool = True
    gms_see_pms: bool = True
    village_name: str = 'Village'           # Display name for village faction
    elim_name: str = 'Elims'                # Display name for eliminator faction


@dataclass
class RoleConfig:
    """Role-specific settings for Tyrian and other game modes."""
    game_mode: str = 'all'                  # 'all', 'tyrian', etc.
    seeker_mode: str = 'both'               # 'role_only', 'alignment_only', 'both'
    thug_mode: str = 'survive'              # 'survive', 'delayed_phase', 'delayed_cycle'
    coinshot_ammo: int = 0                  # 0 = unlimited
    smoker_phase: str = 'both'              # When Smoker can change target
    tineye_phase: str = 'night'             # When Tineye can submit message
    pm_enabling_roles: list[str] = field(default_factory=lambda: ['Tineye'])


@dataclass
class Channels:
    """Discord channel and thread IDs."""
    game_channel_id: Optional[int] = None
    dead_spec_thread_id: Optional[int] = None
    elim_discussion_thread_id: Optional[int] = None
    pm_threads: dict[frozenset, int] = field(default_factory=dict)


@dataclass
class Game:
    """Represents an elimination game instance."""
    guild_id: int
    
    # Sub-configurations
    config: GameConfig = field(default_factory=GameConfig)
    roles: RoleConfig = field(default_factory=RoleConfig)
    channels: Channels = field(default_factory=Channels)
    
    # People
    gm_ids: list[int] = field(default_factory=list)
    players: dict[int, Player] = field(default_factory=dict)
    spectators: list[int] = field(default_factory=list)
    
    # Game state
    status: str = 'setup'  # 'setup', 'active', 'ended'
    phase: str = 'Day 0'   # 'Day' or 'Night'
    day_number: int = 0
    phase_end_time: Optional[datetime] = None
    warnings_sent: set = field(default_factory=set)
    
    # Game metadata
    game_tag: Optional[str] = None
    flavor_name: Optional[str] = None
    
    # Voting
    votes: dict[int, dict[int, int | str]] = field(default_factory=dict)
    eliminated: list[int] = field(default_factory=list)
    vote_history: list[dict] = field(default_factory=list)  # [{day, result_text, eliminated_id, ...}]
    
    # Night Actions - {day_number: {action_type: [(actor_id, target_id, extra_data)]}}
    night_actions: dict[int, dict[str, list]] = field(default_factory=dict)
    
    # Day Actions (Rioter/Soother) - {day_number: {action_type: [(actor_id, target_id, extra_data)]}}
    day_actions: dict[int, dict[str, list]] = field(default_factory=dict)
    
    # Role-specific tracking
    smoker_targets: dict[int, Optional[int]] = field(default_factory=dict)
    smoker_active: dict[int, bool] = field(default_factory=dict)
    thug_used: set[int] = field(default_factory=set)
    delayed_deaths: list[tuple[int, int, str]] = field(default_factory=list)
    lurcher_last_targets: dict[int, int] = field(default_factory=dict)
    mistborn_powers_used: dict[int, list[str]] = field(default_factory=dict)
    mistborn_current_power: dict[int, Optional[str]] = field(default_factory=dict)
    tineye_messages: dict[int, str] = field(default_factory=dict)
    coinshot_kills_used: dict[int, int] = field(default_factory=dict)
    
    # Action results (for GM PM feedback)
    action_results: dict[int, list[str]] = field(default_factory=dict)
    
    # Anonymous mode
    available_identities: list[str] = field(default_factory=lambda: list(ANON_IDENTITIES.keys()))
    
    # ===== HELPER METHODS =====
    
    def get_player_display_name(self, user_id: int) -> str:
        """Get the appropriate display name based on game mode."""
        player = self.players.get(user_id)
        if not player:
            return "Unknown"
        
        if self.config.anon_mode and player.anon_identity:
            return player.anon_identity
        return player.display_name
    
    def get_faction_name(self, alignment: str) -> str:
        """Get the display name for a faction (village/elims)."""
        if alignment == 'village':
            return self.config.village_name
        elif alignment == 'elims':
            return self.config.elim_name
        return alignment.title() if alignment else "Unknown"
    
    def get_player_role_display(self, user_id: int) -> str:
        """Get 'FactionName RoleName' for a player (e.g., 'Village Tineye' or 'Spiked Lurcher')."""
        player = self.players.get(user_id)
        if not player:
            return "Unknown"
        
        faction = self.get_faction_name(player.alignment)
        role = player.role or 'Vanilla'
        return f"{faction} {role}"
    
    def get_current_phase_type(self) -> str:
        """Get current phase type: 'Day' or 'Night'."""
        return 'Day' if 'Day' in self.phase else 'Night'
    
    def is_day(self) -> bool:
        """Check if it's currently day phase."""
        return 'Day' in self.phase
    
    def is_night(self) -> bool:
        """Check if it's currently night phase."""
        return 'Night' in self.phase
    
    def is_allowed_phase(self, allowed: str) -> bool:
        """Check if current phase matches allowed setting."""
        if allowed == 'both':
            return True
        return allowed.lower() == self.get_current_phase_type().lower()
    
    def get_alive_players(self) -> list[Player]:
        """Get all living players."""
        return [p for p in self.players.values() if p.is_alive]
    
    def get_alive_count(self) -> tuple[int, int]:
        """Get count of alive village and elim players."""
        alive = self.get_alive_players()
        village = sum(1 for p in alive if p.alignment == 'village')
        elims = sum(1 for p in alive if p.alignment == 'elims')
        return village, elims
    
    def check_win_condition(self) -> Optional[str]:
        """Check if either side has won. Returns 'village', 'elims', 'last_standing', or None."""
        village_count, elim_count = self.get_alive_count()
        alive_players = self.get_alive_players()
        
        # Last man standing - only one player left
        if self.config.win_condition == 'last_man_standing':
            if len(alive_players) == 1:
                return 'last_standing'
            return None
        
        # Village wins if all elims dead
        if elim_count == 0:
            return 'village'
        
        # Elims win at parity or overparity
        if self.config.win_condition == 'parity':
            if elim_count >= village_count:
                return 'elims'
        else:  # overparity
            if elim_count > village_count:
                return 'elims'
        
        return None
    
    def get_day_votes(self) -> dict[int, int | str]:
        """Get votes for current day."""
        return self.votes.get(self.day_number, {})
    
    def tally_votes(self) -> dict[int | str, list[int]]:
        """Tally votes for current day. Returns {target_id: [voter_ids]}."""
        day_votes = self.get_day_votes()
        tally = {}
        for voter_id, target_id in day_votes.items():
            if target_id not in tally:
                tally[target_id] = []
            tally[target_id].append(voter_id)
        return tally
    
    def get_pm_thread_key(self, player1_id: int, player2_id: int) -> frozenset:
        """Get the key for a PM thread between two players."""
        return frozenset({player1_id, player2_id})
    
    def get_pm_thread_id(self, player1_id: int, player2_id: int) -> Optional[int]:
        """Get existing PM thread ID between two players, or None."""
        key = self.get_pm_thread_key(player1_id, player2_id)
        return self.channels.pm_threads.get(key)
    
    def are_pms_available(self) -> bool:
        """Check if PMs are currently available based on settings and roles."""
        if not self.config.pms_enabled:
            return False
        
        # If no enabling roles specified, PMs are always available
        if not self.roles.pm_enabling_roles:
            return True
        
        # Check if any player with an enabling role is alive
        for player in self.players.values():
            if player.is_alive and player.role in self.roles.pm_enabling_roles:
                return True
        
        return False
    
    def add_night_action(self, action_type: str, actor_id: int, target_id: int, extra_data: any = None):
        """Record a night action. Replaces any existing action of same type from same actor."""
        if self.day_number not in self.night_actions:
            self.night_actions[self.day_number] = {}
        if action_type not in self.night_actions[self.day_number]:
            self.night_actions[self.day_number][action_type] = []
        
        # Remove any existing action from this actor
        self.night_actions[self.day_number][action_type] = [
            action for action in self.night_actions[self.day_number][action_type]
            if action[0] != actor_id
        ]
        # Add new action
        self.night_actions[self.day_number][action_type].append((actor_id, target_id, extra_data))
    
    def add_day_action(self, action_type: str, actor_id: int, target_id: int, extra_data: any = None):
        """Record a day action (Rioter/Soother). Replaces any existing action of same type from same actor."""
        if self.day_number not in self.day_actions:
            self.day_actions[self.day_number] = {}
        if action_type not in self.day_actions[self.day_number]:
            self.day_actions[self.day_number][action_type] = []
        
        # Remove any existing action from this actor
        self.day_actions[self.day_number][action_type] = [
            action for action in self.day_actions[self.day_number][action_type]
            if action[0] != actor_id
        ]
        # Add new action
        self.day_actions[self.day_number][action_type].append((actor_id, target_id, extra_data))
    
    def get_night_actions(self, action_type: str = None) -> list | dict:
        """Get night actions for current day."""
        day_actions = self.night_actions.get(self.day_number, {})
        if action_type:
            return day_actions.get(action_type, [])
        return day_actions
    
    def get_day_actions(self, action_type: str = None) -> list | dict:
        """Get day actions for current day."""
        day_act = self.day_actions.get(self.day_number, {})
        if action_type:
            return day_act.get(action_type, [])
        return day_act
    
    def is_smoked(self, player_id: int) -> bool:
        """Check if a player is protected by a Smoker."""
        # Check if player is a Smoker themselves
        player = self.players.get(player_id)
        if player and player.role == 'Smoker' and self.smoker_active.get(player_id, True):
            return True
        
        # Check if protected by another Smoker
        for smoker_id, target_id in self.smoker_targets.items():
            if target_id == player_id:
                smoker = self.players.get(smoker_id)
                if smoker and smoker.is_alive and self.smoker_active.get(smoker_id, True):
                    return True
        
        return False
    
    def add_action_result(self, player_id: int, message: str):
        """Add a result message to be sent to a player's GM-PM."""
        if player_id not in self.action_results:
            self.action_results[player_id] = []
        self.action_results[player_id].append(message)
    
    def clear_action_results(self):
        """Clear all action results after they've been sent."""
        self.action_results = {}
    
    def get_players_with_role(self, role: str, alive_only: bool = True) -> list[Player]:
        """Get all players with a specific role."""
        players = []
        for player in self.players.values():
            if player.role == role:
                if not alive_only or player.is_alive:
                    players.append(player)
        return players


def get_game(guild_id: int) -> Optional[Game]:
    """Get the game for a guild, or None if no game exists."""
    return games.get(guild_id)


def create_game(guild_id: int, creator_id: int) -> Game:
    """Create a new game for a guild."""
    game = Game(guild_id=guild_id, gm_ids=[creator_id])
    games[guild_id] = game
    return game


def delete_game(guild_id: int) -> bool:
    """Delete a game. Returns True if game existed."""
    if guild_id in games:
        del games[guild_id]
        return True
    return False