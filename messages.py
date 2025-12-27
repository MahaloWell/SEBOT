"""
Centralized user-facing messages for SEBOT.
All response strings in one place for consistency and easy modification.
"""

# ===== ERROR MESSAGES =====

class Errors:
    """Error messages shown to users."""
    
    # General errors
    NO_GAME = "❌ No game exists in this server!"
    GAME_NOT_ACTIVE = "❌ Game is not active!"
    NOT_IN_GAME = "❌ You are not in this game!"
    DEAD_PLAYER = "❌ Dead players cannot use abilities!"
    
    # Channel errors
    WRONG_CHANNEL = "❌ Actions can only be submitted in your GM-PM thread!"
    ACTIONS_IN_PM = "❌ Use `!actions` in your GM-PM thread to see your role abilities!"
    USE_PM_THREAD = "❌ Use this command in your private GM-PM thread!"
    
    # Phase errors
    NIGHT_ONLY = "❌ You can only use this ability at night!"
    DAY_ONLY = "❌ You can only use this ability during the day!"
    
    # Target errors
    NO_SELF_TARGET = "❌ You cannot target yourself!"
    PLAYER_NOT_FOUND = "❌ Player not found!"
    PLAYER_DEAD = "❌ That player is dead!"
    
    # Role errors
    WRONG_ROLE = "❌ You don't have the role to use this action!"
    NO_POWER_YET = "❌ You haven't been assigned a power yet!"
    
    # Vote errors
    ALREADY_VOTED = "❌ You have already voted!"
    NO_VOTE_TO_REMOVE = "❌ You don't have a vote to remove!"
    VOTING_CLOSED = "❌ Voting is not open!"
    
    # Anonymous mode errors
    ANON_NOT_ENABLED = "❌ Anonymous mode is not enabled!"
    SAY_IN_PM_ONLY = "❌ Use `!say` in your private GM-PM thread!"
    
    # PM errors  
    PMS_DISABLED = "❌ PMs are currently disabled!"
    PM_SELF = "❌ You cannot PM yourself!"
    
    # Role-specific errors
    LURCHER_CONSECUTIVE = "❌ You cannot protect the same player consecutively!"
    RIOT_SELF_VOTE = "❌ You cannot redirect your own vote with Riot!"
    SOOTHE_SELF = "❌ You cannot Soothe your own vote!"
    COINSHOT_NO_AMMO = "❌ You have used all your Coinshot ammunition ({ammo} kill(s))!"
    
    # Mistborn errors
    MISTBORN_WRONG_POWER = "❌ Your current Mistborn power is not {power}!"
    
    # Usage errors
    @staticmethod
    def usage(command: str, example: str = None) -> str:
        msg = f"❌ Usage: `{command}`"
        if example:
            msg += f"\nExample: `{example}`"
        return msg


# ===== SUCCESS MESSAGES =====

class Success:
    """Success/confirmation messages."""
    
    # Voting
    @staticmethod
    def vote_cast(target: str) -> str:
        return f"✅ Vote cast for **{target}**"
    
    @staticmethod
    def vote_removed() -> str:
        return "✅ Vote removed."
    
    @staticmethod
    def vote_changed(old: str, new: str) -> str:
        return f"✅ Vote changed from **{old}** to **{new}**"
    
    # Role actions
    @staticmethod
    def coinshot(target: str, ammo_remaining: int = None) -> str:
        msg = f"🔫 Coinshot target submitted: **{target}**"
        if ammo_remaining is not None:
            msg += f"\n*(Ammo remaining after this action: {ammo_remaining})*"
        return msg
    
    @staticmethod
    def lurcher(target: str) -> str:
        return f"🛡️ Protection target submitted: **{target}**"
    
    @staticmethod
    def riot(target: str, new_target: str) -> str:
        return (
            f"😤 Riot submitted: **{target}**'s vote will be redirected to **{new_target}**\n"
            f"⚠️ Your own vote will be cancelled."
        )
    
    @staticmethod
    def soothe(target: str) -> str:
        return f"😶 Soothe submitted: **{target}**'s vote will be cancelled."
    
    @staticmethod
    def seek(target: str) -> str:
        return f"🔍 Investigation target submitted: **{target}**"
    
    @staticmethod
    def smoke_activated(target: str = None) -> str:
        if target:
            return f"🌫️ Smoker activated. You and **{target}** are protected."
        return "🌫️ Smoker activated. You are protected from Rioting, Soothing, and Seeking."
    
    @staticmethod
    def smoke_deactivated() -> str:
        return "🌫️ Smoker deactivated. You and your target are no longer protected."
    
    @staticmethod
    def smoke_target(target: str) -> str:
        return f"🌫️ You are now also protecting **{target}** from Rioting, Soothing, and Seeking."
    
    @staticmethod
    def tineye_submitted(message: str, updated: bool = False) -> str:
        action = "updated" if updated else "recorded"
        return (
            f"📜 Your anonymous message has been **{action}**. "
            f"It will appear at the start of the next day.\n"
            f"Message: *{message}*"
        )
    
    # Kill (elim)
    @staticmethod
    def kill_submitted(target: str) -> str:
        return f"✅ Night kill submitted for **{target}**"
    
    @staticmethod
    def kill_none() -> str:
        return "✅ Night kill: **No Kill** (you chose not to kill)"


# ===== INFO MESSAGES =====

class Info:
    """Informational messages."""
    
    @staticmethod
    def smoker_status(active: bool, target: str = None) -> str:
        target_name = target if target else "No one else"
        return (
            f"🌫️ **Smoker Status:**\n"
            f"• Active: {'Yes' if active else 'No'}\n"
            f"• Also protecting: {target_name}\n\n"
            f"Commands:\n"
            f"• `!smoke+` - Activate (protect self)\n"
            f"• `!smoke-` - Deactivate (no protection)\n"
            f"• `!smoke [player]` - Also protect another player"
        )
    
    @staticmethod
    def tineye_current(message: str) -> str:
        return (
            f"📜 **Your current Tineye message:**\n*{message}*\n\n"
            f"Use `!tin [new message]` to change it."
        )
    
    @staticmethod
    def tineye_none() -> str:
        return (
            f"📜 You haven't submitted a message yet.\n"
            f"Use `!tin [message]` or `!tinpost [message]` to submit one."
        )


# ===== GAME ANNOUNCEMENTS =====

class Announcements:
    """Public game announcements."""
    
    @staticmethod
    def player_killed(name: str, alignment: str, role: str) -> str:
        return (
            f"💀 **{name} has been killed!**\n"
            f"They were: **{alignment.title()} - {role or 'Vanilla'}**"
        )
    
    @staticmethod
    def player_eliminated(name: str, alignment: str, role: str) -> str:
        return (
            f"⚖️ **{name} has been eliminated!**\n"
            f"They were: **{alignment.title()} - {role or 'Vanilla'}**"
        )
    
    @staticmethod
    def player_survived(name: str) -> str:
        return f"🛡️ **{name} was attacked but survived!**"
    
    @staticmethod
    def no_death() -> str:
        return "🛡️ **No one died during the night.**"
    
    @staticmethod
    def no_elimination() -> str:
        return "**No one was eliminated today.**"
    
    @staticmethod
    def delayed_death(name: str, alignment: str, role: str) -> str:
        return (
            f"💀 **{name} has succumbed to their wounds!**\n"
            f"They were: **{alignment.title()} - {role or 'Vanilla'}**"
        )
    
    @staticmethod
    def day_start(day_num: int, kill_msg: str, tineye_msg: str = None) -> str:
        announcement = f"☀️ **Day {day_num} begins!**\n\n{kill_msg}"
        if tineye_msg:
            announcement += f"\n{tineye_msg}"
        announcement += "\n\nDiscussion and voting are now open."
        return announcement
    
    @staticmethod
    def night_start(day_num: int) -> str:
        return f"🌙 **Night {day_num} begins...**"


# ===== ACTION RESULTS (Private) =====

class ActionResults:
    """Private action result messages sent to player PM threads."""
    
    @staticmethod
    def lurcher_save() -> str:
        return "🛡️ Your target was attacked last night. Your protection saved them!"
    
    @staticmethod
    def thug_survive() -> str:
        return "💪 You were attacked but your Thug ability saved you! (One-time use expended)"
    
    @staticmethod
    def thug_delayed_phase() -> str:
        return "💪 You were attacked! Your Thug ability lets you survive one more phase before death."
    
    @staticmethod
    def thug_delayed_cycle() -> str:
        return "💪 You were attacked! Your Thug ability lets you survive one more full cycle before death."
    
    @staticmethod
    def seeker_result(target: str, role: str = None, alignment: str = None) -> str:
        parts = [f"🔍 **Investigation Result for {target}:**"]
        if role:
            parts.append(f"**Role:** {role}")
        if alignment:
            parts.append(f"**Alignment:** {alignment.title()}")
        return "\n".join(parts)
    
    @staticmethod
    def seeker_blocked(target: str) -> str:
        return f"🔍 Your investigation of **{target}** was blocked. They were protected from your abilities."
    
    @staticmethod
    def soothe_success(target: str) -> str:
        return f"😶 You successfully Soothed **{target}**'s vote."
    
    @staticmethod
    def soothe_blocked() -> str:
        return "😶 Your Soothe was blocked. The target was protected from your influence."
    
    @staticmethod
    def riot_success(target: str, new_target: str) -> str:
        return f"😤 You successfully Rioted **{target}**'s vote to **{new_target}**."
    
    @staticmethod
    def riot_blocked() -> str:
        return "😤 Your Riot was blocked. The target was protected from your influence. Your vote is still cancelled."
    
    @staticmethod
    def mistborn_power(day: int, power: str) -> str:
        return (
            f"🎲 **Your Mistborn power for Day {day}: {power}**\n"
            f"Use the `!{power.lower()}` command to use this ability."
        )


# ===== COMMAND USAGE =====

class Usage:
    """Command usage strings."""
    
    COINSHOT = "!coinshot [player]` or `!cs [player]"
    LURCHER = "!lurcher [player]` or `!lurch [player]"
    RIOT = "!riot [player] to [new target]"
    RIOT_EXAMPLE = "!riot Amber Vulture to Crimson Wolf"
    SOOTHE = "!soothe [player]"
    SEEK = "!seek [player]"
    SMOKE = "!smoke [player]`, `!smoke+`, or `!smoke-"
    TINEYE = "!tin [message]` or `!tinpost [message]"
    VOTE = "!vote [player]"
    KILL = "!kill [player]` or `!kill none"
    SAY = "!say [message]"
    PM = "!pm [player] [message]"