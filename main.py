import os
import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timezone, timedelta

# ⚙️ CONFIGURATION (Change les IDs ici)
FORUM_CHANNEL_ID = 1469712424578973716  # ID de ton salon forum/blog
AUTO_TAG_ID      = 1496121282687664269  # ID du tag automatique à la création
INACTIVE_TAG_ID  = 1512469541941149867  # ID du tag "Inactif"
RESOLVED_TAG_ID  = 1496121282687664270  # ⚠️ REMPLACE PAR LE VRAI ID du tag "Résolu"

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Bot connecté en tant que {bot.user.name} 🚀")
    if not check_inactivity.is_running():
        check_inactivity.start()

@bot.event
async def on_connect():
    try:
        await bot.tree.sync()
        print("⚡ Commandes Slash synchronisées avec succès !")
    except Exception as e:
        print(f"❌ Erreur de synchronisation des commandes : {e}")

@bot.event
async def on_thread_create(thread: discord.Thread):
    if thread.parent_id == FORUM_CHANNEL_ID:
        tag = thread.parent.get_tag(AUTO_TAG_ID)
        if tag:
            await thread.add_tags(tag, reason="Tag automatique à la création")
            print(f"✨ Tag automatique ajouté au post : {thread.name}")

async def get_last_activity(thread: discord.Thread) -> datetime:
    """Retourne la vraie date du dernier message dans le thread."""
    try:
        async for message in thread.history(limit=1):
            return message.created_at
    except Exception:
        pass
    # Fallback sur la date de création du thread
    return thread.created_at

async def already_sent(thread: discord.Thread, marker: str) -> bool:
    """Vérifie si le bot a déjà envoyé un message contenant `marker`."""
    try:
        async for message in thread.history(limit=10):
            if message.author == bot.user and marker in message.content:
                return True
    except Exception:
        pass
    return False

@tasks.loop(hours=24)
async def check_inactivity():
    forum_channel = bot.get_channel(FORUM_CHANNEL_ID)
    if not forum_channel:
        return

    now = datetime.now(timezone.utc)

    # Threads actifs + threads archivés récents
    all_threads = list(forum_channel.threads)
    try:
        async for thread in forum_channel.archived_threads(limit=100):
            all_threads.append(thread)
    except Exception:
        pass

    for thread in all_threads:
        # Ignorer les threads déjà verrouillés (traités)
        if thread.locked:
            continue

        last_activity = await get_last_activity(thread)
        inactivity_duration = now - last_activity
        creator_id = thread.owner_id

        # ⏳ CAS : 2 mois d'inactivité
        if inactivity_duration >= timedelta(days=60):
            # Eviter le doublon
            if not await already_sent(thread, "~ 2 mois"):
                await thread.send(
                    f"⏳ **Dernière mention** <@{creator_id}> !\n"
                    f"Ce post est inactif depuis **~ 2 mois** malgré nos précédentes relances 📅.\n"
                    f"Le sujet va donc être fermé et va obtenir le tag **Inactif** 🔒.\n"
                    f"Si le problème persiste ou si vous avez à nouveau besoin d'aide, "
                    f"n'hésitez pas à ouvrir un nouveau post dans <#{FORUM_CHANNEL_ID}> ! 🚀✨"
                )
            # Ajout du tag Inactif + archivage + lock
            inactive_tag = thread.parent.get_tag(INACTIVE_TAG_ID)
            tags = list(thread.applied_tags)
            if inactive_tag and inactive_tag not in tags:
                tags.append(inactive_tag)
            await thread.edit(applied_tags=tags, archived=True, locked=True, reason="Inactivité 2 mois")

        # ⏳ CAS : 1 mois d'inactivité (mais pas encore 2 mois)
        elif inactivity_duration >= timedelta(days=30):
            if not await already_sent(thread, "~1 mois"):
                await thread.send(
                    f"⏳ ** Inactivité** <@{creator_id}> !\n"
                    f"Ce post est inactif depuis **~1 mois** 📅.\n"
                    f"Le sujet va donc être archiver dans **7 Jours** automatiquement 🔒"
                )

@bot.tree.command(name="resolu", description="Clôture le post et le marque comme résolu (Modos uniquement)")
@app_commands.checks.has_permissions(manage_threads=True)
async def resolu(interaction: discord.Interaction):
    channel = interaction.channel

    if channel and hasattr(channel, 'parent') and channel.parent and channel.parent.id == FORUM_CHANNEL_ID:
        thread = channel
        creator_id = thread.owner_id

        # 1. Message de confirmation
        await interaction.response.send_message(
            f"Super, dossier classé ! 🎉\n"
            f"Merci pour ton retour <@{creator_id}>. Je passe le post en Résolus. ✅\n"
            f"Si tu as une autre question plus tard, n'hésite pas à ouvrir un nouveau post "
            f"dans <#{FORUM_CHANNEL_ID}> ! 🚀🤝"
        )

        # 2. Tag "Résolu"
        resolved_tag = thread.parent.get_tag(RESOLVED_TAG_ID)
        tags = list(thread.applied_tags)
        if resolved_tag and resolved_tag not in tags:
            tags.append(resolved_tag)

        # 3. Archivage (sans lock pour que le créateur puisse relire)
        await thread.edit(applied_tags=tags, archived=True, locked=False, reason="Commande /resolu par un modo")
    else:
        await interaction.response.send_message(
            "❌ Cette commande ne peut être utilisée que dans un post de ton forum.",
            ephemeral=True
        )

@resolu.error
async def resolu_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.errors.MissingPermissions):
        await interaction.response.send_message(
            "🔒 Tu n'as pas la permission d'utiliser cette commande (Droits de modérateur requis).",
            ephemeral=True
        )

bot.run(os.environ.get("DISCORD_TOKEN"))
