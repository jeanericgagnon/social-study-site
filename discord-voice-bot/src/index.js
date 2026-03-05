import 'dotenv/config';
import {
  Client,
  Events,
  GatewayIntentBits,
  ChannelType,
  PermissionsBitField,
} from 'discord.js';
import {
  joinVoiceChannel,
  getVoiceConnection,
  VoiceConnectionStatus,
  entersState,
} from '@discordjs/voice';

const token = process.env.DISCORD_BOT_TOKEN;
const guildId = process.env.DISCORD_GUILD_ID;

if (!token) {
  console.error('Missing DISCORD_BOT_TOKEN');
  process.exit(1);
}

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildVoiceStates,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
  ],
});

function parseArgs(content) {
  const parts = content.trim().split(/\s+/);
  return { cmd: parts[0]?.toLowerCase(), args: parts.slice(1) };
}

async function joinChannel(message, channel) {
  if (!channel || channel.type !== ChannelType.GuildVoice) {
    await message.reply('I can only join voice channels.');
    return;
  }

  const me = message.guild.members.me;
  const perms = channel.permissionsFor(me);
  if (!perms?.has(PermissionsBitField.Flags.Connect) || !perms?.has(PermissionsBitField.Flags.Speak)) {
    await message.reply('I need Connect + Speak permissions in that voice channel.');
    return;
  }

  const connection = joinVoiceChannel({
    channelId: channel.id,
    guildId: message.guild.id,
    adapterCreator: message.guild.voiceAdapterCreator,
    selfDeaf: false,
    selfMute: false,
  });

  try {
    await entersState(connection, VoiceConnectionStatus.Ready, 15_000);
    await message.reply(`Joined **${channel.name}**.`);
  } catch (err) {
    connection.destroy();
    await message.reply(`Failed to join ${channel.name}: ${err.message}`);
  }
}

client.once(Events.ClientReady, (c) => {
  console.log(`Voice bot online as ${c.user.tag}`);
});

client.on(Events.MessageCreate, async (message) => {
  if (message.author.bot) return;
  if (!message.guild) return;
  if (guildId && message.guild.id !== guildId) return;

  const { cmd, args } = parseArgs(message.content);

  if (cmd === '!voice-status') {
    const conn = getVoiceConnection(message.guild.id);
    if (!conn) {
      await message.reply('Not connected to any voice channel.');
      return;
    }
    await message.reply(`Connected. State: **${conn.state.status}**`);
    return;
  }

  if (cmd === '!voice-join') {
    const target = args.join(' ');
    const byName = target
      ? message.guild.channels.cache.find(
          (c) => c.type === ChannelType.GuildVoice && c.name.toLowerCase() === target.toLowerCase(),
        )
      : null;

    const fromUser = message.member?.voice?.channel;
    const channel = byName || fromUser;

    await joinChannel(message, channel);
    return;
  }

  if (cmd === '!voice-leave') {
    const conn = getVoiceConnection(message.guild.id);
    if (!conn) {
      await message.reply('I am not in a voice channel.');
      return;
    }
    conn.destroy();
    await message.reply('Left voice channel.');
    return;
  }
});

client.login(token);
