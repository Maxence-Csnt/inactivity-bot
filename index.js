const { Client, GatewayIntentBits, ChannelType, PermissionFlagsBits } = require('discord.js');

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
  ],
});

// ─── CONFIG ──────────────────────────────────────────────────────────────────
const config = {
  token: process.env.DISCORD_TOKEN,

  // Salon forum de support
  forumChannelId: 'TON_ID_FORUM',

  // Salon où ouvrir de nouveaux posts
  newPostChannelId: '1469712424578973716',

  // Noms des tags (doivent exister dans le forum)
  inactiveTagName:    'Inactif',
  resolvedTagName:    'Résolu',
  helpTagName:        'Demande d\'aide',

  // Délais
  oneMonthMs:  30 * 24 * 60 * 60 * 1000,
  twoMonthsMs: 60 * 24 * 60 * 60 * 1000,

  // Intervalle de vérification (toutes les heures)
  checkIntervalMs: 60 * 60 * 1000,
};
// ─────────────────────────────────────────────────────────────────────────────

const notified = new Map();

// Utilitaire : remplace un tag par un autre dans un thread
async function swapTag(thread, forum, removeTagName, addTagName) {
  const removeTag = forum.availableTags.find(t => t.name === removeTagName);
  const addTag    = forum.availableTags.find(t => t.name === addTagName);
  let tags = [...thread.appliedTags];
  if (removeTag) tags = tags.filter(id => id !== removeTag.id);
  if (addTag && !tags.includes(addTag.id)) tags.push(addTag.id);
  await thread.setAppliedTags(tags).catch(console.error);
}

// ── Tag "Demande d'aide" à la création d'un post ──────────────────────────
client.on('threadCreate', async (thread) => {
  if (!thread.parentId || thread.parentId !== config.forumChannelId) return;

  const forum = await client.channels.fetch(config.forumChannelId).catch(() => null);
  if (!forum) return;

  const helpTag = forum.availableTags.find(t => t.name === config.helpTagName);
  if (!helpTag) return;

  const tags = [...thread.appliedTags];
  if (!tags.includes(helpTag.id)) {
    await thread.setAppliedTags([...tags, helpTag.id]).catch(console.error);
  }

  console.log(`[nouveau post] Tag "${config.helpTagName}" appliqué : ${thread.name}`);
});

// ── Commande !resolu (modos uniquement) ──────────────────────────────────
client.on('messageCreate', async (msg) => {
  if (msg.author.bot) return;

  // Réinitialise le timer d'inactivité si quelqu'un répond
  if (msg.channel.isThread()) {
    const state = notified.get(msg.channel.id);
    if (state && !state.warned2months) state.warned1month = false;
  }

  // Commande !resolu
  if (msg.content.toLowerCase() !== '!resolu') return;
  if (!msg.channel.isThread()) return;
  if (msg.channel.parentId !== config.forumChannelId) return;

  // Vérifie que l'auteur est modo (permission Manage Messages)
  const member = await msg.guild.members.fetch(msg.author.id).catch(() => null);
  if (!member || !member.permissions.has(PermissionFlagsBits.ManageMessages)) {
    await msg.reply('❌ Tu n\'as pas la permission d\'utiliser cette commande.').catch(() => {});
    return;
  }

  const thread = msg.channel;
  const forum  = await client.channels.fetch(config.forumChannelId).catch(() => null);
  if (!forum) return;

  // Swap tag Demande d'aide → Résolu
  await swapTag(thread, forum, config.helpTagName, config.resolvedTagName);

  // Message de clôture
  await thread.send(
    `Super, dossier classé ! 🎉\n` +
    `Merci pour ton retour <@${thread.ownerId}>. Je passe le post en Résolus. ✅\n` +
    `Si tu as une autre question plus tard, n'hésite pas à ouvrir un nouveau post dans <#${config.newPostChannelId}> ! 🚀🤝`
  );

  // Archive et verrouille
  await thread.setArchived(true).catch(console.error);
  await thread.setLocked(true).catch(console.error);

  console.log(`[!resolu] Thread clôturé : ${thread.name}`);
});

// ── Vérification d'inactivité ─────────────────────────────────────────────
async function checkInactiveThreads() {
  const forum = await client.channels.fetch(config.forumChannelId).catch(() => null);
  if (!forum || forum.type !== ChannelType.GuildForum) {
    console.error('Forum introuvable ou mauvais type.');
    return;
  }

  const inactiveTag = forum.availableTags.find(t => t.name === config.inactiveTagName);
  const activeThreads = await forum.threads.fetchActive();
  const now = Date.now();

  for (const [id, thread] of activeThreads.threads) {
    if (!notified.has(id)) notified.set(id, { warned1month: false, warned2months: false });
    const state = notified.get(id);

    const messages = await thread.messages.fetch({ limit: 1 }).catch(() => null);
    if (!messages || messages.size === 0) continue;

    const elapsed = now - (messages.size > 0 ? messages.first().createdTimestamp : thread.createdTimestamp);

    // ── 2 MOIS ──
    if (elapsed >= config.twoMonthsMs && !state.warned2months) {
      state.warned2months = true;

      await thread.send(
        `⏳ **Dernière mention** <@${thread.ownerId}> !\n` +
        `Ce post est inactif depuis **~ 2 mois** malgré nos précédentes relances 📅.\n` +
        `Le sujet va donc être fermé et va obtenir le tag **Inactif** 🔒.\n` +
        `Si le problème persiste ou si vous avez à nouveau besoin d'aide, n'hésitez pas à ouvrir un nouveau post dans <#${config.newPostChannelId}> ! 🚀✨`
      );

      await swapTag(thread, forum, config.helpTagName, config.inactiveTagName);
      await thread.setArchived(true).catch(console.error);
      await thread.setLocked(true).catch(console.error);

      console.log(`[2 mois] Thread fermé : ${thread.name}`);
    }

    // ── 1 MOIS ──
    else if (elapsed >= config.oneMonthMs && !state.warned1month) {
      state.warned1month = true;

      await thread.send(
        `⏳ **Inactivité** <@${thread.ownerId}> !\n` +
        `Ce post est inactif depuis **~1 mois** 📅.\n` +
        `Le sujet va donc être archiver dans **7 Jours** automatiquement 🔒`
      );

      console.log(`[1 mois] Avertissement envoyé : ${thread.name}`);
    }
  }
}

client.once('ready', () => {
  console.log(`✅ Connecté en tant que ${client.user.tag}`);
  checkInactiveThreads();
  setInterval(checkInactiveThreads, config.checkIntervalMs);
});

client.login(config.token);
