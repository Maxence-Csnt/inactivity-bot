const { Client, GatewayIntentBits, ChannelType } = require('discord.js');

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

  // Salon forum de support (remplace par ton ID)
  forumChannelId: '1496121282687664268',

  // Salon où ouvrir de nouveaux posts (utilisé dans le message 2 mois)
  newPostChannelId: '1469712424578973716',

  // Tag "Inactif" à appliquer (nom exact du tag dans le forum)
  inactiveTagName: 'Inactif',

  // Délais
  oneMonthMs:  10 * 1000,   // 10 secondes
  twoMonthsMs: 20 * 1000,   // 20 secondes

  // Intervalle de vérification (toutes les heures)
  checkIntervalMs: 5 * 1000,  // toutes les 5 secondes
};
// ─────────────────────────────────────────────────────────────────────────────

// Garde en mémoire les posts déjà notifiés pour éviter les doublons
// Structure : { threadId: { warned1month: bool, warned2months: bool } }
const notified = new Map();

async function checkInactiveThreads() {
  const forum = await client.channels.fetch(config.forumChannelId).catch(() => null);
  if (!forum || forum.type !== ChannelType.GuildForum) {
    console.error('Forum introuvable ou mauvais type.');
    return;
  }

  // Récupère les tags du forum pour trouver l'ID du tag "Inactif"
  const inactiveTag = forum.availableTags.find(t => t.name === config.inactiveTagName);

  const activeThreads = await forum.threads.fetchActive();
  const now = Date.now();

  for (const [id, thread] of activeThreads.threads) {
    if (!notified.has(id)) notified.set(id, { warned1month: false, warned2months: false });
    const state = notified.get(id);

    // Dernier message du thread
    const messages = await thread.messages.fetch({ limit: 1 }).catch(() => null);
    if (!messages || messages.size === 0) continue;

    const lastMsg = messages.first();
    const lastActivity = lastMsg.createdTimestamp;
    const elapsed = now - lastActivity;

    // ── 2 MOIS ──
    if (elapsed >= config.twoMonthsMs && !state.warned2months) {
      state.warned2months = true;

      const owner = thread.ownerId;
      await thread.send(
        `⏳ **Dernière mention** <@${owner}> !\n` +
        `Ce post est inactif depuis **~ 2 mois** malgré nos précédentes relances 📅.\n` +
        `Le sujet va donc être fermé et va obtenir le tag **Inactif** 🔒.\n` +
        `Si le problème persiste ou si vous avez à nouveau besoin d'aide, n'hésitez pas à ouvrir un nouveau post dans <#${config.newPostChannelId}> ! 🚀✨`
      );

      // Applique le tag "Inactif" si trouvé
      if (inactiveTag) {
        const currentTags = thread.appliedTags.filter(t => t !== inactiveTag.id);
        await thread.setAppliedTags([...currentTags, inactiveTag.id]).catch(console.error);
      }

      // Archive/ferme le thread
      await thread.setArchived(true).catch(console.error);
      await thread.setLocked(true).catch(console.error);

      console.log(`[2 mois] Thread fermé : ${thread.name}`);
    }

    // ── 1 MOIS ──
    else if (elapsed >= config.oneMonthMs && !state.warned1month) {
      state.warned1month = true;

      const owner = thread.ownerId;
      await thread.send(
        `⏳ **Inactivité** <@${owner}> !\n` +
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

// Réinitialise le suivi quand un nouveau message est posté dans un thread
client.on('messageCreate', (msg) => {
  if (!msg.channel.isThread()) return;
  const state = notified.get(msg.channel.id);
  if (!state) return;
  // Si quelqu'un répond, on réinitialise le timer 1 mois (pas le 2 mois si déjà atteint)
  if (!state.warned2months) {
    state.warned1month = false;
  }
});

client.login(config.token);
