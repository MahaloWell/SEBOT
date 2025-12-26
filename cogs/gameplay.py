"""Gameplay commands - voting, kills, phase management."""

import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import random

from helpers.game_state import games, get_game, delete_game
from helpers.permissions import is_gm_or_im, gm_only, require_game, get_gm_role, get_im_role
from helpers.matching import parse_vote_target, parse_kill_target
from helpers.anonymous import get_or_create_webhook, announce_vote
from helpers.utils import (
    format_time_remaining, update_game_channel_permissions, 
    archive_game, add_user_to_thread_safe, close_all_pm_threads
)
from helpers.role_actions import (
    process_night_actions, apply_vote_modifications, 
    format_vote_count_with_modifications, send_action_results,
    format_tineye_messages, assign_mistborn_power
)
from data.identities import ANON_IDENTITIES


class GameplayCog(commands.Cog):
    """Commands for active gameplay."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.phase_timer_checker.start()
    
    def cog_unload(self):
        self.phase_timer_checker.cancel()
    
    # ===== PHASE TIMER =====
    
    @tasks.loop(seconds=10)
    async def phase_timer_checker(self):
        """Check all active games for phase transitions and warnings."""
        for guild_id, game in list(games.items()):
            if game.status != 'active' or not game.phase_end_time:
                continue
            
            if not game.auto_phase_transition:
                continue
            
            now = datetime.now()
            time_remaining = (game.phase_end_time - now).total_seconds()
            
            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue
            
            game_channel = guild.get_channel(game.game_channel_id)
            if not game_channel:
                continue
            
            # Send warnings
            warnings = game.warnings_sent
            
            warning_thresholds = [
                (295, 305, '5min', "⏰ **5 minutes remaining** in this phase!"),
                (115, 125, '2min', "⏰ **2 minutes remaining** in this phase!"),
                (55, 65, '1min', "⏰ **1 minute remaining** in this phase!"),
                (5, 15, '10sec', "⏰ **10 seconds remaining** in this phase!")
            ]
            
            for min_time, max_time, key, message in warning_thresholds:
                if min_time <= time_remaining < max_time and key not in warnings:
                    await self._send_phase_warnings(guild, game, game_channel, message, key)
            
            # Time's up
            if time_remaining <= 0:
                await self._auto_end_phase(guild, game)
    
    async def _send_phase_warnings(self, guild, game, game_channel, message, key):
        """Send warning messages to relevant channels."""
        await game_channel.send(message)
        
        if game.phase == 'Night':
            # Warn elims about pending kill
            night_actions = game.night_actions.get(game.day_number, {})
            if not night_actions.get('elim_kill') and game.elim_discussion_thread_id:
                elim_thread = guild.get_thread(game.elim_discussion_thread_id)
                if elim_thread:
                    await elim_thread.send(
                        f"{message}\n⚠️ **Reminder:** You haven't submitted a kill yet! "
                        f"Use `!kill [player]` or `!kill none`"
                    )
        
        elif game.phase == 'Day' and game.anon_mode:
            # Warn players who haven't voted
            day_votes = game.get_day_votes()
            for user_id, player in game.players.items():
                if player.is_alive and user_id not in day_votes:
                    if player.private_channel_id:
                        private_thread = guild.get_thread(player.private_channel_id)
                        if private_thread:
                            await private_thread.send(
                                f"{message}\n⚠️ **Reminder:** You haven't voted yet! "
                                f"Use `!vote [player]`{' or `!vote none`' if game.allow_no_elimination else ''}"
                            )
        
        game.warnings_sent.add(key)
    
    async def _auto_end_phase(self, guild, game):
        """Automatically end the current phase."""
        game_channel = guild.get_channel(game.game_channel_id)
        dead_spec_thread = None
        if game.dead_spec_thread_id:
            dead_spec_thread = guild.get_thread(game.dead_spec_thread_id)
        
        try:
            if game.phase == 'Day':
                await self._process_day_end(guild, game, game_channel, dead_spec_thread)
            else:
                await self._process_night_end(guild, game, game_channel, dead_spec_thread)
        except Exception as e:
            print(f"Error in auto_end_phase: {e}")
            import traceback
            traceback.print_exc()
            if game_channel:
                await game_channel.send("❌ Error processing automatic phase end. Please contact a GM.")
    
    def _format_final_vote_count(self, game) -> str:
        """Format a complete vote record for end of day with Riot/Soothe effects."""
        # Use the new vote modification function that handles Rioter/Soother
        return format_vote_count_with_modifications(game)
    
    async def _check_pm_closure(self, guild, game, game_channel) -> None:
        """Check if PMs should be closed after a death (role-based PM disabling)."""
        # Only matters if there are PM-enabling roles configured
        if not game.pm_enabling_roles:
            return
        
        # Check if PMs are still available
        if not game.are_pms_available():
            # Close all PM threads
            closed_count = await close_all_pm_threads(guild, game)
            if closed_count > 0 and game_channel:
                await game_channel.send(
                    f"🔒 **PMs have been disabled!** {closed_count} PM thread(s) have been closed."
                )
    
    async def _process_day_end(self, guild, game, game_channel, dead_spec_thread):
        """Process end of day phase - handle elimination."""
        day_votes = game.get_day_votes()
        
        # Generate vote count before elimination (includes Riot/Soothe effects in totals)
        vote_count_msg = self._format_final_vote_count(game)
        
        elimination_msg = await self._resolve_elimination(guild, game, day_votes, dead_spec_thread)
        
        # Process delayed deaths (Thug delayed_phase dying at night start, delayed_cycle from execution)
        delayed_death_msgs = await self._process_delayed_deaths(guild, game, dead_spec_thread, 'night', game.day_number)
        
        # Build full announcement
        announcement = f"☀️ **Day {game.day_number} has ended.**\n\n{vote_count_msg}\n\n{elimination_msg}"
        
        if delayed_death_msgs:
            announcement += "\n\n" + "\n\n".join(delayed_death_msgs)
        
        announcement += f"\n\n🌙 **Night {game.day_number} begins...**"
        
        if game_channel:
            await game_channel.send(announcement)
        
        # Send action results (Riot/Soothe feedback, Thug survival)
        await send_action_results(guild, game)
        
        await update_game_channel_permissions(guild, game)
        
        # Check if PMs should be closed
        await self._check_pm_closure(guild, game, game_channel)
        
        # Check win
        winner = game.check_win_condition()
        if winner:
            await self._handle_game_over(guild, game, game_channel, winner)
            return
        
        # Transition to night
        game.phase = 'Night'
        game.phase_end_time = datetime.now() + timedelta(minutes=game.night_length_minutes)
        game.warnings_sent = set()
    
    async def _process_delayed_deaths(self, guild, game, dead_spec_thread, phase_type, day_num):
        """
        Process delayed Thug deaths.
        phase_type: 'day' (processing at day start) or 'night' (processing at night start)
        day_num: the day number we're entering
        Returns list of death announcement messages.
        """
        messages = []
        remaining_deaths = []
        
        for player_id, trigger_day, trigger_phase in game.delayed_deaths:
            if trigger_day == day_num and trigger_phase == phase_type:
                # Time to die
                player = game.players.get(player_id)
                if player and player.is_alive:
                    player.is_alive = False
                    game.eliminated.append(player_id)
                    
                    player_name = game.get_player_display_name(player_id)
                    messages.append(
                        f"💀 **{player_name} has succumbed to their wounds!**\n"
                        f"They were: **{player.alignment.title()} - {player.role or 'Vanilla'}**"
                    )
                    
                    if dead_spec_thread:
                        member = guild.get_member(player_id)
                        if member:
                            await add_user_to_thread_safe(dead_spec_thread, member)
            else:
                remaining_deaths.append((player_id, trigger_day, trigger_phase))
        
        game.delayed_deaths = remaining_deaths
        return messages
    
    async def _resolve_elimination(self, guild, game, day_votes, dead_spec_thread):
        """Resolve day phase elimination. Returns announcement message."""
        min_votes = game.min_votes_to_eliminate
        
        # Get effective votes after Riot/Soothe modifications
        effective_votes = apply_vote_modifications(game)
        
        if not effective_votes:
            if min_votes == -1:
                return await self._random_elimination(guild, game, dead_spec_thread)
            return "**No votes were cast. No one was eliminated.**"
        
        max_votes = max(effective_votes.values())
        top_voted = [tid for tid, count in effective_votes.items() if count == max_votes]
        
        # Check minimum threshold
        if min_votes > 0 and max_votes < min_votes:
            return (
                f"**No one was eliminated today.** "
                f"(Minimum {min_votes} vote{'s' if min_votes != 1 else ''} required, only {max_votes} received)"
            )
        
        # Vote none in top?
        if 'vote_none' in top_voted:
            return "**No one was eliminated today.** (Vote for no elimination won)"
        
        # Get player votes only
        player_votes = [tid for tid in top_voted if tid != 'vote_none']
        
        if not player_votes:
            return "**No one was eliminated today.**"
        
        # Random tiebreaker
        eliminated_id = random.choice(player_votes)
        return await self._eliminate_player(guild, game, eliminated_id, dead_spec_thread, is_execution=True)
    
    async def _random_elimination(self, guild, game, dead_spec_thread):
        """Perform random elimination when no votes cast and min_votes=-1."""
        alive_players = [uid for uid, p in game.players.items() if p.is_alive]
        if not alive_players:
            return "**No votes were cast. No one was eliminated.**"
        
        eliminated_id = random.choice(alive_players)
        msg = await self._eliminate_player(guild, game, eliminated_id, dead_spec_thread, is_execution=True)
        return msg.replace("has been eliminated!", "has been randomly eliminated!** (No votes were cast)")
    
    async def _eliminate_player(self, guild, game, user_id, dead_spec_thread, is_execution=False):
        """Eliminate a player and return announcement message."""
        player = game.players[user_id]
        player_name = game.get_player_display_name(user_id)
        
        # Check for Thug survival on execution
        if is_execution and player.role == 'Thug' and user_id not in game.thug_used:
            game.thug_used.add(user_id)
            
            if game.thug_mode == 'survive':
                game.add_action_result(
                    user_id,
                    "💪 You were executed but your Thug ability saved you! (One-time use expended)"
                )
                return (
                    f"🛡️ **{player_name} was targeted for elimination but survived!**\n"
                    f"*(They were attacked but lived)*"
                )
            elif game.thug_mode == 'delayed_phase':
                # Executed during Day X -> survive Night X -> die at Day X+1 start
                game.delayed_deaths.append((user_id, game.day_number + 1, 'day'))
                game.add_action_result(
                    user_id,
                    "💪 You were executed! Your Thug ability lets you survive one more phase before death."
                )
                return (
                    f"🛡️ **{player_name} was targeted for elimination but survived!**\n"
                    f"*(They were attacked but lived)*"
                )
            elif game.thug_mode == 'delayed_cycle':
                # Executed during Day X -> survive Night X, Day X+1 -> die at Night X+1 start
                game.delayed_deaths.append((user_id, game.day_number + 1, 'night'))
                game.add_action_result(
                    user_id,
                    "💪 You were executed! Your Thug ability lets you survive one more full cycle before death."
                )
                return (
                    f"🛡️ **{player_name} was targeted for elimination but survived!**\n"
                    f"*(They were attacked but lived)*"
                )
        
        # Normal elimination
        player.is_alive = False
        game.eliminated.append(user_id)
        
        # Add to dead/spec thread
        if dead_spec_thread:
            member = guild.get_member(user_id)
            if member:
                await add_user_to_thread_safe(dead_spec_thread, member)
        
        return (
            f"💀 **{player_name} has been eliminated!**\n"
            f"They were: **{player.alignment.title()} - {player.role or 'Vanilla'}**"
        )
    
    async def _process_night_end(self, guild, game, game_channel, dead_spec_thread):
        """Process end of night phase - handle all role actions and kills."""
        
        # Process all night actions (kills, protections, investigations)
        results = await process_night_actions(guild, game)
        
        # Advance to next day
        game.day_number += 1
        game.phase = 'Day'
        game.phase_end_time = datetime.now() + timedelta(minutes=game.day_length_minutes)
        game.warnings_sent = set()
        
        # Build kill/death messages
        death_messages = []
        save_messages = []
        
        for target_id, role, alignment in results['deaths']:
            player = game.players[target_id]
            player.is_alive = False
            game.eliminated.append(target_id)
            
            player_name = game.get_player_display_name(target_id)
            death_messages.append(
                f"💀 **{player_name} was killed during the night!**\n"
                f"They were: **{alignment.title()} - {role or 'Vanilla'}**"
            )
            
            if dead_spec_thread:
                member = guild.get_member(target_id)
                if member:
                    await add_user_to_thread_safe(dead_spec_thread, member)
        
        for target_id in results['saves']:
            player_name = game.get_player_display_name(target_id)
            save_messages.append(f"🛡️ **{player_name} was attacked but survived!**")
        
        # Process delayed deaths (Thug delayed_cycle or delayed_phase from night attacks)
        delayed_death_msgs = await self._process_delayed_deaths(guild, game, dead_spec_thread, 'day', game.day_number)
        
        # Format output
        if death_messages:
            kill_msg = "\n\n".join(death_messages)
        elif save_messages:
            kill_msg = "\n".join(save_messages)
        else:
            kill_msg = "🛡️ **No one died during the night.**"
        
        # Add save messages if there were also deaths
        if save_messages and death_messages:
            kill_msg += "\n\n" + "\n".join(save_messages)
        
        # Add delayed death messages
        if delayed_death_msgs:
            kill_msg += "\n\n" + "\n\n".join(delayed_death_msgs)
        
        # Get Tineye messages
        tineye_msg = format_tineye_messages(game)
        
        # Assign Mistborn powers for new day
        mistborn_msgs = []
        for player_id, player in game.players.items():
            if player.is_alive and player.role == 'Mistborn':
                power = assign_mistborn_power(game, player_id)
                if power:
                    game.add_action_result(
                        player_id,
                        f"🎲 **Your Mistborn power for Day {game.day_number}: {power}**\n"
                        f"Use the `!{power.lower()}` command to use this ability."
                    )
        
        # Build day start announcement
        announcement = f"☀️ **Day {game.day_number} begins!**\n\n{kill_msg}"
        
        if tineye_msg:
            announcement += f"\n{tineye_msg}"
        
        announcement += "\n\nDiscussion and voting are now open."
        
        if game_channel:
            await game_channel.send(announcement)
        
        # Send action results to players' GM-PM threads
        await send_action_results(guild, game)
        
        await update_game_channel_permissions(guild, game)
        
        # Check if PMs should be closed
        await self._check_pm_closure(guild, game, game_channel)
        
        # Check win
        winner = game.check_win_condition()
        if winner:
            await self._handle_game_over(guild, game, game_channel, winner)
    
    async def _handle_game_over(self, guild, game, game_channel, winner):
        """Handle game ending."""
        if game_channel:
            if winner == 'last_standing':
                # Find the sole survivor
                survivors = [p for p in game.players.values() if p.is_alive]
                if survivors:
                    survivor = survivors[0]
                    winner_name = game.get_player_display_name(survivor.user_id)
                    await game_channel.send(
                        f"🎊 **GAME OVER!**\n"
                        f"**{winner_name}** is the last one standing and wins!\n\n"
                        f"Archiving game channels..."
                    )
                else:
                    await game_channel.send(
                        f"🎊 **GAME OVER!**\n"
                        f"No one survived!\n\n"
                        f"Archiving game channels..."
                    )
            else:
                await game_channel.send(
                    f"🎊 **GAME OVER!**\n"
                    f"**{winner.title()} has won!**\n\n"
                    f"Archiving game channels..."
                )
        
        game.status = 'ended'
        await archive_game(guild, game)
        delete_game(guild.id)
    
    # ===== SLASH COMMANDS =====
    
    @app_commands.command(name="time_remaining", description="Check how much time is left in the current phase")
    @require_game(status='active')
    async def time_remaining(self, interaction: discord.Interaction):
        """Show time remaining in current phase."""
        game = get_game(interaction.guild_id)
        
        time_left = format_time_remaining(game.phase_end_time)
        auto_status = "🤖 Automatic" if game.auto_phase_transition else "👤 Manual"
        
        await interaction.response.send_message(
            f"⏰ **Current Phase:** {game.phase} {game.day_number}\n"
            f"**Time Remaining:** {time_left}\n"
            f"**Phase Transitions:** {auto_status}"
        )
    
    @app_commands.command(name="vote_count", description="Show current vote tallies")
    @require_game(status='active')
    async def vote_count(self, interaction: discord.Interaction):
        """Display current vote count."""
        game = get_game(interaction.guild_id)
        
        if game.phase != 'Day':
            await interaction.response.send_message("❌ No voting during night phase!", ephemeral=True)
            return
        
        day_votes = game.get_day_votes()
        
        if not day_votes:
            await interaction.response.send_message("📊 No votes cast yet today.")
            return
        
        # Tally
        tally = game.tally_votes()
        
        vote_lines = []
        for target_id, voter_ids in sorted(tally.items(), key=lambda x: len(x[1]), reverse=True):
            if target_id == 'vote_none':
                target_name = "No One"
            else:
                target_name = game.get_player_display_name(target_id)
            
            voter_names = [game.get_player_display_name(vid) for vid in voter_ids]
            vote_lines.append(f"**{target_name}** ({len(voter_ids)}): {', '.join(voter_names)}")
        
        alive_count = len([p for p in game.players.values() if p.is_alive])
        
        await interaction.response.send_message(
            f"📊 **Vote Count - Day {game.day_number}**\n"
            f"Time remaining: {format_time_remaining(game.phase_end_time)}\n\n"
            f"{chr(10).join(vote_lines)}\n\n"
            f"Total votes: {len(day_votes)}/{alive_count}"
        )
    
    @app_commands.command(name="clear_votes", description="[GM/IM] Clear all votes for current day")
    @gm_only()
    @require_game(status='active')
    async def clear_votes(self, interaction: discord.Interaction):
        """Clear all votes."""
        game = get_game(interaction.guild_id)
        
        if game.day_number in game.votes:
            game.votes[game.day_number] = {}
        
        await interaction.response.send_message("✅ All votes cleared!")
    
    @app_commands.command(name="end_phase", description="[GM/IM] Manually end the current phase")
    @gm_only()
    @require_game(status='active')
    async def end_phase(self, interaction: discord.Interaction):
        """End current phase and transition to next."""
        game = get_game(interaction.guild_id)
        
        await interaction.response.defer()
        await self._auto_end_phase(interaction.guild, game)
        await interaction.followup.send("✅ Phase manually ended.")


async def setup(bot: commands.Bot):
    await bot.add_cog(GameplayCog(bot))