import os
import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timezone, timedelta

# ⚙️ CONFIGURATION DES CONFIGURATIONS (Change les IDs ici)
FORUM_CHANNEL_ID = 1496121282687664268  # ID de ton salon forum/blog
AUTO_TAG_ID = 1496121282687664269      # ID du tag automatique à la création
INACTIVE_TAG_ID = 1512469541941149867  # ID du tag "Inactif"
RESOLVED_TAG_ID = 1496121282687664270  # ID du tag "Résolu"

# Configuration des permissions du bot
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Bot connecté en tant que {bot.user.name} 🚀")
    # Lance la vérification automatique de l'inactivité tous les jours
    if not check_inactivity.is_running():
        check_inactivity.start()

@bot.event
async def on_connect():
    # Synchronise les commandes Slash (comme /resolu) avec Discord
    try:
        await bot.tree.sync()
        print("⚡ Commandes Slash synchronisées avec succès !")
    except Exception as e:
        print(f"❌ Erreur de synchronisation des commandes : {e}")

---

### 1️⃣ Tag Automatique à la Création 🏷️

@bot.event
async def on_thread_create(thread: discord.Thread):
    if thread.parent_id == FORUM_CHANNEL_ID:
        tag = thread.parent.get_tag(AUTO_TAG_ID)
        if tag:
            await thread.add_tags(tag, reason="Tag automatique à la création")
            print(f"✨ Tag automatique ajouté au post : {thread.name}")

---

### 2️⃣ Gestion de l'inactivité (1 mois et 2 mois) 📅

@tasks.loop(hours=24)
async def check_inactivity():
    forum_channel = bot.get_channel(FORUM_CHANNEL_ID)
    if not forum_channel:
        return

    now = datetime.now(timezone.utc)
    
    # On parcourt tous les posts ouverts (non archivés)
    for thread in forum_channel.threads:
        last_message_time = thread.archive_timestamp
        
        if thread.last_message_id:
            try:
                last_msg = await thread.fetch_message(thread.last_message_id)
                last_message_time = last_msg.created_at
            except discord.NotFound:
                pass

        inactivity_duration = now - last_message_time
        creator_id = thread.owner_id

        # ⏳ CAS : Inactif depuis ~2 mois (60 jours) -> Fermeture
        if inactivity_duration >= timedelta(days=60):
            if not any(t.id == INACTIVE_TAG_ID for t in thread.applied_tags):
                await thread.send(
                    f"⏳ **Dernière mention** <@{creator_id}> !\n"
                    f"Ce post est inactif depuis **~ 2 mois** malgré nos précédentes relances 📅.\n"
                    f"Le sujet va donc être fermé et va obtenir le tag **Inactif** 🔒.\n"
                    f"Si le problème persiste ou si vous avez à nouveau besoin d'aide, n'hésitez pas à ouvrir un nouveau post dans <#{FORUM_CHANNEL_ID}> ! 🚀✨"
                )
                
                # Appliquer le tag Inactif et fermer le post
                inactive_tag = thread.parent.get_tag(INACTIVE_TAG_ID)
                tags = [t for t in thread.applied_tags]
                if inactive_tag and inactive_tag not in tags:
                    tags.append(inactive_tag)
                
                await thread.edit(applied_tags=tags, archived=True, locked=False, reason="Inactivité 2 mois")

        # ⏳ CAS : Inactif depuis ~1 mois (30 jours) -> Relance
        elif inactivity_duration >= timedelta(days=30):
            # Évite d'envoyer le message en boucle s'il a déjà été mis
            already_warned = False
            async for message in thread.history(limit=5):
                if "Ce post est inactif depuis **~1 mois**" in message.content:
                    already_warned = True
                    break
            
            if not already_warned:
                await thread.send(
                    f"⏳ ** Inactivité** <@{creator_id}> !\n"
                    f"Ce post est inactif depuis **~1 mois** 📅.\n"
                    f"Le sujet va donc être archiver dans **7 Jours** automatiquement 🔒"
                )

---

### 3️⃣ Commande de Résolution (Modérateurs uniquement) 🛠️

@bot.tree.command(name="resolu", description="Clôture le post et le marque comme résolu (Modos uniquement)")
@app_commands.checks.has_permissions(manage_threads=True)  # Seuls les modérateurs peuvent le faire
async def resolu(interaction: discord.Interaction):
    if isinstance(interaction.channel, discord.Thread) and interaction.channel.parent_id == FORUM_CHANNEL_ID:
        thread = interaction.channel
        creator_id = thread.owner_id
        
        # Message de clôture
        await interaction.response.send_message(
            f"Super, dossier classé ! 🎉\n"
            f"Merci pour ton retour <@{creator_id}>. Je passe le post en Résolus. ✅\n"
            f"Si tu as une autre question plus tard, n'hésite pas à ouvrir un nouveau post dans <#{FORUM_CHANNEL_ID}> ! 🚀🤝"
        )
        
        # Gestion des tags pour mettre "Résolu"
        resolved_tag = thread.parent.get_tag(RESOLVED_TAG_ID)
        tags = [t for t in thread.applied_tags]
        if resolved_tag and resolved_tag not in tags:
            tags.append(resolved_tag)
            
        # Archive le post proprement
        await thread.edit(applied_tags=tags, archived=True, locked=False)
    else:
        await interaction.response.send_message("❌ Cette commande ne peut être utilisée que dans un post de ton forum.", ephemeral=True)

# Gestion de l'erreur si quelqu'un d'autre essaie la commande slash
@resolu.error
async def resolu_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.errors.MissingPermissions):
        await interaction.response.send_message("🔒 Tu n'as pas la permission d'utiliser cette commande (Droits de modérateur requis).", ephemeral=True)

# 🔑 Lancement via la variable d'environnement Railway
bot.run(os.environ.get("DISCORD_TOKEN"))
