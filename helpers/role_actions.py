"""
Role action processing for SEBOT.
Handles night action resolution, day action effects, and vote modifications.
"""

import random
from typing import Optional
from data.roles import ROLE_DEFINITIONS, RESOLUTION_ORDER


async def process_night_actions(guild, game) -> dict:
    """
    Process all night actions in resolution order.
    Returns dict with results:
    {
        'kills': [(player_id, killer_type)],  # killer_type: 'elim', 'coinshot'
        'saves': [player_id],  # Players who were attacked but saved
        'deaths': [(player_id, role, alignment)],  # Confirmed deaths
    }
    """
    results = {
        'kills': [],
        'saves': [],
        'deaths': [],
    }
    
    night_actions = game.night_actions.get(game.day_number, {})
    
    # Collect all kill targets
    kill_targets = {}  # {target_id: [killer_ids]}
    
    # Elim kill
    elim_kills = night_actions.get('elim_kill', [])
    for actor_id, target_id, _ in elim_kills:
        if target_id and target_id != 'kill_none':
            if target_id not in kill_targets:
                kill_targets[target_id] = []
            kill_targets[target_id].append(('elim', actor_id))
    
    # Coinshot kills - track ammo usage
    coinshot_kills = night_actions.get('kill', [])
    coinshots_used = set()  # Track which coinshots have submitted (for ammo tracking)
    for actor_id, target_id, _ in coinshot_kills:
        if target_id and target_id != 'kill_none':
            if target_id not in kill_targets:
                kill_targets[target_id] = []
            kill_targets[target_id].append(('coinshot', actor_id))
            coinshots_used.add(actor_id)
    
    # Increment ammo used for all coinshots who submitted a kill
    for actor_id in coinshots_used:
        if actor_id not in game.coinshot_kills_used:
            game.coinshot_kills_used[actor_id] = 0
        game.coinshot_kills_used[actor_id] += 1
    
    # Collect protections
    protections = {}  # {target_id: [protector_ids]}
    
    lurcher_protects = night_actions.get('protect', [])
    for actor_id, target_id, _ in lurcher_protects:
        if target_id:
            if target_id not in protections:
                protections[target_id] = []
            protections[target_id].append(actor_id)
    
    # Process each kill target
    for target_id, killers in kill_targets.items():
        player = game.players.get(target_id)
        if not player or not player.is_alive:
            continue
        
        # Track remaining kills after protections
        remaining_kills = len(killers)
        lurcher_saved = False
        
        # Check for Lurcher protection (blocks one kill)
        if target_id in protections and protections[target_id]:
            remaining_kills -= 1
            lurcher_saved = True
            
            # Notify the Lurcher(s)
            for protector_id in protections[target_id]:
                game.add_action_result(
                    protector_id,
                    f"🛡️ Your target was attacked last night. Your protection saved them!"
                )
        
        # If no remaining kills, they survived
        if remaining_kills <= 0:
            results['saves'].append(target_id)
            continue
        
        # Check for Thug survival
        if player.role == 'Thug' and target_id not in game.thug_used:
            game.thug_used.add(target_id)
            results['saves'].append(target_id)
            
            if game.roles.thug_mode == 'survive':
                game.add_action_result(
                    target_id,
                    "💪 You were attacked but your Thug ability saved you! (One-time use expended)"
                )
                continue
            elif game.roles.thug_mode == 'delayed_phase':
                # Attacked during Night X -> survive Day X+1 -> die at Night X+1 start
                game.delayed_deaths.append((target_id, game.day_number + 1, 'night'))
                game.add_action_result(
                    target_id,
                    "💪 You were attacked! Your Thug ability lets you survive one more phase before death."
                )
                continue
            elif game.roles.thug_mode == 'delayed_cycle':
                # Attacked during Night X -> survive Day X+1, Night X+1 -> die at Day X+2 start
                game.delayed_deaths.append((target_id, game.day_number + 2, 'day'))
                game.add_action_result(
                    target_id,
                    "💪 You were attacked! Your Thug ability lets you survive one more full cycle before death."
                )
                continue
        
        # Player dies
        results['deaths'].append((target_id, player.role, player.alignment))
        for killer_type, killer_id in killers:
            results['kills'].append((target_id, killer_type))
            break  # Only record one kill per target
    
    # Process Seeker investigations
    seek_actions = night_actions.get('investigate', [])
    for actor_id, target_id, _ in seek_actions:
        if not target_id:
            continue
        
        target_player = game.players.get(target_id)
        seeker = game.players.get(actor_id)
        
        if not target_player or not seeker or not seeker.is_alive:
            continue
        
        # Check if target is smoked
        if game.is_smoked(target_id):
            game.add_action_result(
                actor_id,
                f"🔍 Your investigation was blocked by interference. You learned nothing."
            )
            continue
        
        # Build result based on seeker_mode
        target_name = game.get_player_display_name(target_id)
        
        if game.roles.seeker_mode == 'role_only':
            game.add_action_result(
                actor_id,
                f"🔍 **{target_name}** has the role: **{target_player.role or 'Vanilla'}**"
            )
        elif game.roles.seeker_mode == 'alignment_only':
            faction = game.get_faction_name(target_player.alignment)
            game.add_action_result(
                actor_id,
                f"🔍 **{target_name}** is aligned with: **{faction}**"
            )
        else:  # both
            faction = game.get_faction_name(target_player.alignment)
            game.add_action_result(
                actor_id,
                f"🔍 **{target_name}** is **{faction}** - **{target_player.role or 'Vanilla'}**"
            )
    
    return results


def calculate_effective_votes(game, add_results: bool = False) -> dict:
    """
    Calculate effective votes after Rioter/Soother effects.
    Returns modified vote tally: {target_id: effective_vote_count}
    
    If add_results is True, also queues action feedback for players.
    """
    raw_votes = game.get_day_votes().copy()
    day_actions = game.day_actions.get(game.day_number, {})
    
    # Track vote modifications
    cancelled_votes = set()  # voter_ids whose votes are cancelled
    redirected_votes = {}  # {voter_id: new_target_id}
    rioter_votes_cancelled = set()  # rioters who used their power (lose their vote)
    
    # Process Soother actions (cancel votes)
    soothe_actions = day_actions.get('cancel_vote', [])
    for actor_id, target_id, _ in soothe_actions:
        if not target_id:
            continue
        
        target_player = game.players.get(target_id)
        actor = game.players.get(actor_id)
        
        if not target_player or not actor or not actor.is_alive:
            continue
        
        # Check if target is smoked
        if game.is_smoked(target_id):
            if add_results:
                game.add_action_result(
                    actor_id,
                    f"😶 Your Soothe was blocked. The target was protected from your influence."
                )
            continue
        
        cancelled_votes.add(target_id)
        if add_results:
            game.add_action_result(
                actor_id,
                f"😶 You successfully Soothed **{game.get_player_display_name(target_id)}**'s vote."
            )
    
    # Process Rioter actions (redirect votes)
    riot_actions = day_actions.get('redirect_vote', [])
    for actor_id, target_id, new_target_id in riot_actions:
        if not target_id or not new_target_id:
            continue
        
        target_player = game.players.get(target_id)
        actor = game.players.get(actor_id)
        
        if not target_player or not actor or not actor.is_alive:
            continue
        
        # Rioter loses their own vote
        rioter_votes_cancelled.add(actor_id)
        
        # Check if target is smoked
        if game.is_smoked(target_id):
            if add_results:
                game.add_action_result(
                    actor_id,
                    f"😤 Your Riot was blocked. The target was protected from your influence. Your vote is still cancelled."
                )
            continue
        
        redirected_votes[target_id] = new_target_id
        if add_results:
            game.add_action_result(
                actor_id,
                f"😤 You successfully Rioted **{game.get_player_display_name(target_id)}**'s vote to **{game.get_player_display_name(new_target_id)}**."
            )
    
    # Calculate effective votes
    effective_votes = {}  # {target_id: count}
    
    for voter_id, target_id in raw_votes.items():
        # Skip if voter's vote was cancelled by Soother
        if voter_id in cancelled_votes:
            continue
        
        # Skip if voter is a Rioter who used their power
        if voter_id in rioter_votes_cancelled:
            continue
        
        # Check if this vote was redirected
        if voter_id in redirected_votes:
            target_id = redirected_votes[voter_id]
        
        if target_id not in effective_votes:
            effective_votes[target_id] = 0
        effective_votes[target_id] += 1
    
    return effective_votes


def apply_vote_modifications(game) -> dict:
    """
    Apply Rioter/Soother effects to votes and queue action feedback.
    Returns modified vote tally: {target_id: effective_vote_count}
    """
    return calculate_effective_votes(game, add_results=True)


def format_vote_count_with_modifications(game) -> str:
    """
    Format vote count showing raw votes but calculated totals.
    Shows who voted for whom, but totals reflect Riot/Soothe effects.
    
    Key behavior:
    - Shows effective vote COUNT (after Riot/Soothe)
    - Shows raw voter NAMES (who publicly voted for each target)
    - If a target has effective votes but no raw votes (from Riot redirect),
      they appear with the count but no names listed
    
    Does NOT add action results (use apply_vote_modifications for that).
    """
    raw_votes = game.get_day_votes()
    effective_votes = calculate_effective_votes(game, add_results=False)
    
    # Group raw votes by target
    raw_vote_groups = {}
    for voter_id, target_id in raw_votes.items():
        if target_id not in raw_vote_groups:
            raw_vote_groups[target_id] = []
        raw_vote_groups[target_id].append(voter_id)
    
    # Find all targets (union of raw and effective)
    all_targets = set(raw_vote_groups.keys()) | set(effective_votes.keys())
    
    # Find players who didn't vote
    alive_players = [uid for uid, p in game.players.items() if p.is_alive]
    abstainers = [uid for uid in alive_players if uid not in raw_votes]
    
    lines = ["📊 **Final Vote Count**"]
    
    # Sort by effective vote count (descending), then by target name
    sorted_targets = sorted(
        all_targets,
        key=lambda t: (effective_votes.get(t, 0), str(t)),
        reverse=True
    )
    
    for target_id in sorted_targets:
        effective_count = effective_votes.get(target_id, 0)
        
        # Skip targets with 0 effective votes (their votes were Soothed/redirected away)
        if effective_count == 0:
            continue
        
        # Get target name
        if target_id == 'vote_none':
            target_name = "No Elimination"
        else:
            target_name = game.get_player_display_name(target_id)
        
        # Get raw voter names (only those who publicly voted for this target)
        raw_voters = raw_vote_groups.get(target_id, [])
        voter_names = [game.get_player_display_name(vid) for vid in raw_voters]
        
        # Show effective count with raw voter names
        # If no raw voters (vote came from Riot), names list will be empty
        if voter_names:
            lines.append(f"**{target_name}** ({effective_count}): {', '.join(voter_names)}")
        else:
            # Target only has votes from Riot redirects - show count but no names
            lines.append(f"**{target_name}** ({effective_count}):")
    
    # Add abstainers
    if abstainers:
        abstainer_names = [game.get_player_display_name(uid) for uid in abstainers]
        lines.append(f"**No Vote** ({len(abstainers)}): {', '.join(abstainer_names)}")
    
    return "\n".join(lines)


def assign_mistborn_power(game, player_id: int) -> Optional[str]:
    """
    Assign a random power to a Mistborn for the current day.
    Returns the assigned power name, or None if all powers used.
    """
    all_powers = ROLE_DEFINITIONS['Mistborn']['powers_pool']
    
    # Get powers already used by this Mistborn
    used = game.mistborn_powers_used.get(player_id, [])
    
    # If all powers used, reset
    if len(used) >= len(all_powers):
        game.mistborn_powers_used[player_id] = []
        used = []
    
    # Get available powers
    available = [p for p in all_powers if p not in used]
    
    if not available:
        return None
    
    # Pick random power
    power = random.choice(available)
    
    # Record usage
    if player_id not in game.mistborn_powers_used:
        game.mistborn_powers_used[player_id] = []
    game.mistborn_powers_used[player_id].append(power)
    game.mistborn_current_power[player_id] = power
    
    return power


def get_current_mistborn_power(game, player_id: int) -> Optional[str]:
    """Get the current power a Mistborn has access to."""
    return game.mistborn_current_power.get(player_id)


async def send_action_results(guild, game):
    """Send all queued action results to players' GM-PM threads."""
    for player_id, messages in game.action_results.items():
        player = game.players.get(player_id)
        if not player or not player.private_channel_id:
            continue
        
        thread = guild.get_thread(player.private_channel_id)
        if not thread:
            continue
        
        for message in messages:
            try:
                await thread.send(message)
            except Exception as e:
                print(f"Error sending action result to {player_id}: {e}")
    
    game.clear_action_results()


def format_tineye_messages(game) -> str:
    """Format Tineye anonymous messages for day start announcement."""
    if not game.tineye_messages:
        return ""
    
    messages = list(game.tineye_messages.values())
    
    if not messages:
        return ""
    
    lines = ["\n📜 **Anonymous Messages:**"]
    for i, msg in enumerate(messages):
        if i > 0:
            lines.append("---")
        lines.append(f"*{msg}*")
    
    # Clear messages after formatting
    game.tineye_messages = {}
    
    return "\n".join(lines)


def can_use_role_action(game, player_id: int, action_type: str) -> tuple[bool, str]:
    """
    Check if a player can use a specific role action.
    Returns (can_use, error_message).
    """
    player = game.players.get(player_id)
    if not player:
        return False, "You are not in this game."
    
    if not player.is_alive:
        return False, "Dead players cannot use actions."
    
    role = player.role
    
    # Check Mistborn current power
    if role == 'Mistborn':
        current_power = get_current_mistborn_power(game, player_id)
        if not current_power:
            return False, "You haven't been assigned a power yet this day."
        role = current_power  # Use current power for action validation
    
    role_info = ROLE_DEFINITIONS.get(role)
    if not role_info:
        return False, "Your role cannot perform actions."
    
    # Check if this role has the requested action
    if role_info.get('action_type') != action_type:
        return False, f"Your current role ({role}) cannot perform this action."
    
    # Check phase requirements
    required_phase = role_info.get('action_phase')
    current_phase = 'Day' if 'Day' in game.phase else 'Night'
    
    if required_phase == 'night' and current_phase != 'Night':
        return False, "This action can only be used at night."
    
    if required_phase == 'day' and current_phase != 'Day':
        return False, "This action can only be used during the day."
    
    # Check Lurcher consecutive target restriction
    if action_type == 'protect':
        last_target = game.lurcher_last_targets.get(player_id)
        # We'll check against the actual target in the command handler
    
    return True, ""