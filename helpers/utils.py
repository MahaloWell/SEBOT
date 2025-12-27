"""Utility helper functions."""

import discord
from datetime import datetime
from typing import Optional

from helpers.game_state import Game
from helpers.permissions import get_gm_role, get_im_role


def format_time_remaining(end_time: Optional[datetime]) -> str:
    """Format remaining time in a readable way."""
    if not end_time:
        return "No timer set"
    
    now = datetime.now()
    remaining = end_time - now
    
    if remaining.total_seconds() <= 0:
        return "Phase has ended!"
    
    hours = int(remaining.total_seconds() // 3600)
    minutes = int((remaining.total_seconds() % 3600) // 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m remaining"
    else:
        return f"{minutes}m remaining"


async def update_game_channel_permissions(guild: discord.Guild, game: Game) -> None:
    """Update game channel permissions based on living players and game mode."""
    game_channel = guild.get_channel(game.channels.game_channel_id)
    if not game_channel:
        return
    
    gm_role = get_gm_role(guild)
    im_role = get_im_role(guild)
    
    # Base permissions
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(
            read_messages=True,
            send_messages=False,
            create_public_threads=False,
            create_private_threads=False
        ),
        guild.me: discord.PermissionOverwrite(
            read_messages=True,
            send_messages=True,
            create_public_threads=True,
            create_private_threads=True
        )
    }
    
    # GM/IM permissions
    for role in [gm_role, im_role]:
        if role:
            overwrites[role] = discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                create_public_threads=True,
                create_private_threads=True
            )
    
    # In non-anon mode, living players can post
    if not game.config.anon_mode:
        for user_id, player in game.players.items():
            member = guild.get_member(user_id)
            if member and player.is_alive:
                overwrites[member] = discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    create_public_threads=False,
                    create_private_threads=False
                )
    
    await game_channel.edit(overwrites=overwrites)


async def add_user_to_thread_safe(thread: discord.Thread, member: discord.Member) -> bool:
    """Safely add a user to a thread, returning success status."""
    try:
        await thread.add_user(member)
        return True
    except Exception as e:
        print(f"Error adding {member.name} to thread {thread.name}: {e}")
        return False


async def close_all_pm_threads(guild: discord.Guild, game: 'Game') -> int:
    """
    Close (lock and archive) all PM threads.
    Returns count of threads closed.
    """
    closed_count = 0
    
    for thread_id in game.channels.pm_threads.values():
        thread = guild.get_thread(thread_id)
        if thread:
            try:
                await thread.send("🔒 **PMs have been disabled. This thread is now closed.**")
                await thread.edit(locked=True, archived=True)
                closed_count += 1
            except Exception as e:
                print(f"Error closing PM thread {thread_id}: {e}")
    
    return closed_count


async def create_pm_thread(
    guild: discord.Guild,
    game: 'Game',
    player1_id: int,
    player2_id: int
) -> Optional[discord.Thread]:
    """
    Create a PM thread between two players.
    Returns the thread or None if creation failed.
    """
    from helpers.permissions import get_gm_role, get_im_role
    
    game_channel = guild.get_channel(game.channels.game_channel_id)
    if not game_channel:
        return None
    
    player1 = game.players.get(player1_id)
    player2 = game.players.get(player2_id)
    
    if not player1 or not player2:
        return None
    
    # Generate thread name
    if game.config.anon_mode:
        name1 = player1.anon_identity or "Player1"
        name2 = player2.anon_identity or "Player2"
    else:
        name1 = player1.display_name
        name2 = player2.display_name
    
    thread_prefix = game.game_tag.lower() if game.game_tag else "pm"
    thread_name = f"💬-{thread_prefix}-{name1[:10]}-{name2[:10]}"
    
    try:
        pm_thread = await game_channel.create_thread(
            name=thread_name,
            type=discord.ChannelType.private_thread,
            invitable=False
        )
        
        # Add both players
        member1 = guild.get_member(player1_id)
        member2 = guild.get_member(player2_id)
        
        if member1:
            await add_user_to_thread_safe(pm_thread, member1)
        if member2:
            await add_user_to_thread_safe(pm_thread, member2)
        
        # Add GMs/IMs if configured
        if game.config.gms_see_pms:
            gm_role = get_gm_role(guild)
            im_role = get_im_role(guild)
            
            for role in [gm_role, im_role]:
                if role:
                    for member in role.members:
                        await add_user_to_thread_safe(pm_thread, member)
        
        # Store thread reference
        key = game.get_pm_thread_key(player1_id, player2_id)
        game.channels.pm_threads[key] = pm_thread.id
        
        # Send welcome message
        gm_note = " GMs/IMs can see this conversation." if game.config.gms_see_pms else ""
        await pm_thread.send(
            f"💬 **Private conversation between {name1} and {name2}**\n"
            f"You can chat privately here.{gm_note}"
        )
        
        return pm_thread
        
    except Exception as e:
        print(f"Error creating PM thread: {e}")
        return None
        return False


async def archive_game(guild: discord.Guild, game: Game) -> tuple[int, str]:
    """
    Archive all game threads and make them public.
    
    Returns:
        Tuple of (channels archived count, archive category name)
    """
    if not game.channels.game_channel_id:
        return 0, "No channels to archive"
    
    game_channel = guild.get_channel(game.channels.game_channel_id)
    if not game_channel:
        return 0, "Game channel not found"
    
    # Create archive category name
    if game.game_tag and game.flavor_name:
        game_name = f"{game.game_tag} - {game.flavor_name}"
    else:
        game_name = "Archived Game"
    
    archive_category = await guild.create_category(name=f"📁 {game_name}")
    
    try:
        # Move game channel to archive and make public/read-only
        await game_channel.edit(
            category=archive_category,
            sync_permissions=False,
            overwrites={
                guild.default_role: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=False,
                    create_public_threads=True,
                    create_private_threads=False
                ),
                guild.me: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    create_public_threads=True,
                    create_private_threads=True
                )
            }
        )
        
        # Archive and lock all active threads
        for thread in game_channel.threads:
            try:
                if thread.archived:
                    await thread.edit(archived=False)
                await thread.edit(locked=True, archived=True)
            except Exception as e:
                print(f"Error archiving thread {thread.name}: {e}")
        
        # Also handle archived threads
        async for thread in game_channel.archived_threads(limit=100):
            try:
                await thread.edit(archived=False, locked=True)
                await thread.edit(archived=True)
            except Exception as e:
                print(f"Error archiving old thread {thread.name}: {e}")
        
        return 1, archive_category.name
        
    except Exception as e:
        print(f"Error archiving game: {e}")
        return 0, "Error during archiving"