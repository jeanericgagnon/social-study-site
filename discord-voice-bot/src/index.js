import 'dotenv/config';
import {
  Client,
  Events,
  GatewayIntentBits,
  ChannelType,
  PermissionsBitField,
  REST,
  Routes,
  SlashCommandBuilder,
} from 'discord.js';
import {
  joinVoiceChannel,
  getVoiceConnection,
  EndBehaviorType,
  VoiceConnectionStatus,
  entersState,
  createAudioPlayer,
  createAudioResource,
  AudioPlayerStatus,
  StreamType,
} from '@discordjs/voice';
import prism from 'prism-media';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const token = process.env.DISCORD_BOT_TOKEN;
const guildId = process.env.DISCORD_GUILD_ID;
const whisperBin = process.env.WHISPER_BIN || path.resolve('../.venv-whisper/bin/whisper');
const whisperModel = process.env.WHISPER_MODEL || 'base';
const routerUrl = process.env.OPENCLAW_ROUTER_URL || '';
const routerToken = process.env.OPENCLAW_ROUTER_TOKEN || '';
const autoReply = String(process.env.VOICE_AGENT_AUTO_REPLY || 'false').toLowerCase() === 'true';
const ttsEnabled = String(process.env.VOICE_TTS_ENABLED || 'true').toLowerCase() === 'true';
const ttsVoice = process.env.VOICE_TTS_VOICE || 'Samantha';
const maxReplyChars = Number(process.env.VOICE_MAX_REPLY_CHARS || 500);
const minSecondsBetweenTurns = Number(process.env.VOICE_MIN_SECONDS_BETWEEN_TURNS || 2);
const allowedTextChannels = new Set((process.env.VOICE_ALLOWED_TEXT_CHANNEL_IDS || '').split(',').map(s => s.trim()).filter(Boolean));
const allowedVoiceChannels = new Set((process.env.VOICE_ALLOWED_VOICE_CHANNEL_IDS || '').split(',').map(s => s.trim()).filter(Boolean));
const allowedUsers = new Set((process.env.VOICE_ALLOWED_USER_IDS || '').split(',').map(s => s.trim()).filter(Boolean));

if (!token) {
  console.error('Missing DISCORD_BOT_TOKEN');
  process.exit(1);
}

const audioDir = path.resolve('./recordings');
fs.mkdirSync(audioDir, { recursive: true });

const listenState = new Map(); // guildId -> { enabled:boolean, textChannelId:string }
const audioPlayers = new Map(); // guildId -> AudioPlayer
const lastTurnAt = new Map(); // key userId -> epoch ms

const LOG_PREFIX = '[voice-bot]';
function log(event, meta = {}) {
  const line = JSON.stringify({ ts: new Date().toISOString(), event, ...meta });
  console.log(`${LOG_PREFIX} ${line}`);
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

function isAllowedTextChannel(channelId) {
  return allowedTextChannels.size === 0 || allowedTextChannels.has(channelId);
}

function isAllowedVoiceChannel(channelId) {
  return allowedVoiceChannels.size === 0 || allowedVoiceChannels.has(channelId);
}

function isAllowedUser(userId) {
  return allowedUsers.size === 0 || allowedUsers.has(userId);
}

function withinRateLimit(userId) {
  const now = Date.now();
  const last = lastTurnAt.get(userId) || 0;
  if (now - last < minSecondsBetweenTurns * 1000) return false;
  lastTurnAt.set(userId, now);
  return true;
}

function clampReply(text) {
  if (!text) return text;
  return text.length > maxReplyChars ? `${text.slice(0, maxReplyChars)}…` : text;
}

function writeWavHeader(fd, dataLength, sampleRate = 48000, channels = 2, bitsPerSample = 16) {
  const header = Buffer.alloc(44);
  const byteRate = sampleRate * channels * bitsPerSample / 8;
  const blockAlign = channels * bitsPerSample / 8;

  header.write('RIFF', 0);
  header.writeUInt32LE(36 + dataLength, 4);
  header.write('WAVE', 8);
  header.write('fmt ', 12);
  header.writeUInt32LE(16, 16);
  header.writeUInt16LE(1, 20);
  header.writeUInt16LE(channels, 22);
  header.writeUInt32LE(sampleRate, 24);
  header.writeUInt32LE(byteRate, 28);
  header.writeUInt16LE(blockAlign, 32);
  header.writeUInt16LE(bitsPerSample, 34);
  header.write('data', 36);
  header.writeUInt32LE(dataLength, 40);

  fs.writeSync(fd, header, 0, 44, 0);
}

async function transcribeWav(filePath) {
  return new Promise((resolve, reject) => {
    const outDir = path.dirname(filePath);
    const proc = spawn(whisperBin, [
      filePath,
      '--model', whisperModel,
      '--language', 'en',
      '--task', 'transcribe',
      '--output_format', 'txt',
      '--output_dir', outDir,
    ]);

    let stderr = '';
    proc.stderr.on('data', (d) => { stderr += d.toString(); });
    proc.on('close', (code) => {
      if (code !== 0) return reject(new Error(stderr || `whisper exit ${code}`));
      const txtPath = filePath.replace(/\.wav$/, '.txt');
      const text = fs.existsSync(txtPath) ? fs.readFileSync(txtPath, 'utf8').trim() : '';
      resolve(text);
    });
  });
}

async function askOpenClawRouter({ transcript, userId, userName, guildId, textChannelId }) {
  if (!routerUrl) return null;
  const headers = { 'content-type': 'application/json' };
  if (routerToken) headers.authorization = `Bearer ${routerToken}`;

  const res = await fetch(routerUrl, {
    method: 'POST',
    headers,
    body: JSON.stringify({ transcript, userId, userName, guildId, textChannelId, source: 'discord-voice-bot' }),
  });

  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`router ${res.status}: ${body.slice(0, 200)}`);
  }

  const data = await res.json().catch(() => ({}));
  return data.reply || data.message || data.output || null;
}

function ensureAudioPlayer(guildId, connection) {
  let player = audioPlayers.get(guildId);
  if (!player) {
    player = createAudioPlayer();
    player.on('error', (e) => console.error('audio player error', e.message));
    player.on(AudioPlayerStatus.Idle, () => {});
    audioPlayers.set(guildId, player);
  }
  connection.subscribe(player);
  return player;
}

async function speakInCall(connection, guildId, text) {
  if (!ttsEnabled || !text?.trim()) return;
  const ts = Date.now();
  const aiffPath = path.join(audioDir, `${guildId}-${ts}.aiff`);
  const wavPath = path.join(audioDir, `${guildId}-${ts}.wav`);

  await new Promise((resolve, reject) => {
    const p = spawn('say', ['-v', ttsVoice, '-o', aiffPath, text.slice(0, 1200)]);
    p.on('close', (code) => (code === 0 ? resolve() : reject(new Error(`say exit ${code}`))));
  });

  await new Promise((resolve, reject) => {
    const p = spawn('ffmpeg', ['-y', '-i', aiffPath, '-ar', '48000', '-ac', '2', wavPath]);
    p.on('close', (code) => (code === 0 ? resolve() : reject(new Error(`ffmpeg exit ${code}`))));
  });

  const player = ensureAudioPlayer(guildId, connection);
  const resource = createAudioResource(wavPath, {
    inputType: StreamType.Arbitrary,
    inlineVolume: true,
  });
  player.play(resource);
}

async function startReceiver(connection, guild, textChannel) {
  const receiver = connection.receiver;

  receiver.speaking.on('start', (userId) => {
    const state = listenState.get(guild.id);
    if (!state?.enabled) return;
    if (!isAllowedUser(userId)) return;
    if (!withinRateLimit(userId)) return;

    const opusStream = receiver.subscribe(userId, {
      end: {
        behavior: EndBehaviorType.AfterSilence,
        duration: 1200,
      },
    });

    const decoder = new prism.opus.Decoder({
      frameSize: 960,
      channels: 2,
      rate: 48000,
    });

    const ts = Date.now();
    const wavPath = path.join(audioDir, `${guild.id}-${userId}-${ts}.wav`);
    const fd = fs.openSync(wavPath, 'w');
    fs.writeSync(fd, Buffer.alloc(44));

    let dataLength = 0;

    opusStream.pipe(decoder);
    decoder.on('data', (chunk) => {
      dataLength += chunk.length;
      fs.writeSync(fd, chunk);
    });

    decoder.on('end', async () => {
      try {
        writeWavHeader(fd, dataLength);
      } finally {
        fs.closeSync(fd);
      }

      // skip tiny clips
      if (dataLength < 48000) return;

      try {
        const transcript = await transcribeWav(wavPath);
        if (!transcript) return;
        const user = await guild.members.fetch(userId).catch(() => null);
        const name = user?.displayName || user?.user?.username || userId;
        await textChannel.send(`🎙️ **${name}**: ${transcript}`);

        if (autoReply) {
          try {
            const reply = await askOpenClawRouter({
              transcript,
              userId,
              userName: name,
              guildId: guild.id,
              textChannelId: textChannel.id,
            });
            if (reply) {
              const safeReply = clampReply(reply);
              await textChannel.send(`🤖 ${safeReply}`);
              const conn = getVoiceConnection(guild.id);
              if (conn) await speakInCall(conn, guild.id, safeReply).catch(() => {});
            }
          } catch (routerErr) {
            await textChannel.send(`Router error: ${routerErr.message}`);
          }
        }
      } catch (err) {
        await textChannel.send(`STT error for <@${userId}>: ${err.message}`);
      }
    });

    decoder.on('error', async (err) => {
      try { fs.closeSync(fd); } catch {}
      await textChannel.send(`Audio decode error: ${err.message}`);
    });
  });
}

async function joinChannel(message, channel) {
  if (!channel || channel.type !== ChannelType.GuildVoice) {
    await message.reply('I can only join voice channels.');
    return null;
  }
  log('voice_join_attempt', { guildId: message.guild.id, channelId: channel.id, channelName: channel.name });

  const me = message.guild.members.me;
  const perms = channel.permissionsFor(me);
  if (!perms?.has(PermissionsBitField.Flags.Connect) || !perms?.has(PermissionsBitField.Flags.Speak)) {
    await message.reply('I need Connect + Speak permissions in that voice channel.');
    return null;
  }

  const connection = joinVoiceChannel({
    channelId: channel.id,
    guildId: message.guild.id,
    adapterCreator: message.guild.voiceAdapterCreator,
    selfDeaf: false,
    selfMute: false,
  });

  await entersState(connection, VoiceConnectionStatus.Ready, 15_000);
  log('voice_join_ready', { guildId: message.guild.id, channelId: channel.id });

  connection.on('stateChange', (oldState, newState) => {
    if (oldState.status !== newState.status) {
      log('voice_state_change', { guildId: message.guild.id, from: oldState.status, to: newState.status });
    }
  });

  return connection;
}

async function registerSlashCommands(clientUserId) {
  if (!guildId) return;
  const commands = [
    new SlashCommandBuilder().setName('voice-status').setDescription('Check voice bot status'),
    new SlashCommandBuilder().setName('voice-join').setDescription('Join your current voice channel'),
    new SlashCommandBuilder().setName('voice-listen').setDescription('Start transcribing voice chunks'),
    new SlashCommandBuilder().setName('voice-stop').setDescription('Stop transcribing voice chunks'),
    new SlashCommandBuilder().setName('voice-leave').setDescription('Leave voice channel'),
    new SlashCommandBuilder().setName('voice-say').setDescription('Speak text in voice channel')
      .addStringOption(o => o.setName('text').setDescription('Text to speak').setRequired(true)),
  ].map(c => c.toJSON());

  const rest = new REST({ version: '10' }).setToken(token);
  await rest.put(Routes.applicationGuildCommands(clientUserId, guildId), { body: commands });
  log('slash_registered', { guildId, count: commands.length });
}

client.once(Events.ClientReady, async (c) => {
  log('ready', { user: c.user.tag });
  try { await registerSlashCommands(c.user.id); } catch (e) { log('slash_register_error', { message: e.message }); }
});

client.on(Events.Error, (err) => {
  log('client_error', { message: err.message });
});

client.on(Events.ShardDisconnect, (event, id) => {
  log('shard_disconnect', { code: event.code, shardId: id });
});

client.on(Events.ShardReconnecting, (id) => {
  log('shard_reconnecting', { shardId: id });
});

client.on(Events.InteractionCreate, async (interaction) => {
  if (!interaction.isChatInputCommand()) return;
  if (!interaction.guild) return;
  if (guildId && interaction.guild.id !== guildId) return;
  if (!isAllowedTextChannel(interaction.channelId)) return;
  if (!isAllowedUser(interaction.user.id)) return;

  const cmd = interaction.commandName;

  if (cmd === 'voice-status') {
    const conn = getVoiceConnection(interaction.guild.id);
    const state = listenState.get(interaction.guild.id);
    await interaction.reply(conn
      ? `Connected. State: **${conn.state.status}** | Listening: **${state?.enabled ? 'on' : 'off'}**`
      : 'Not connected to any voice channel.');
    return;
  }

  if (cmd === 'voice-join') {
    const channel = interaction.member?.voice?.channel;
    if (!channel || !isAllowedVoiceChannel(channel.id)) {
      await interaction.reply('Join an allowlisted voice channel first.');
      return;
    }
    try {
      await joinChannel({ guild: interaction.guild, member: interaction.member, reply: (t) => interaction.followUp?.(t) }, channel);
      await interaction.reply(`Joined **${channel.name}**.`);
    } catch (err) {
      await interaction.reply(`Failed to join: ${err.message}`);
    }
    return;
  }

  if (cmd === 'voice-listen') {
    const conn = getVoiceConnection(interaction.guild.id);
    if (!conn) return interaction.reply('Join a voice channel first with /voice-join.');
    const currently = listenState.get(interaction.guild.id);
    if (currently?.enabled) return interaction.reply('Already listening.');
    listenState.set(interaction.guild.id, { enabled: true, textChannelId: interaction.channelId });
    await startReceiver(conn, interaction.guild, interaction.channel);
    await interaction.reply('🎧 Listening started.');
    return;
  }

  if (cmd === 'voice-stop') {
    const st = listenState.get(interaction.guild.id);
    if (!st?.enabled) return interaction.reply('Listening is not active.');
    listenState.set(interaction.guild.id, { ...st, enabled: false });
    await interaction.reply('🛑 Listening stopped.');
    return;
  }

  if (cmd === 'voice-leave') {
    const conn = getVoiceConnection(interaction.guild.id);
    if (!conn) return interaction.reply('I am not in a voice channel.');
    listenState.delete(interaction.guild.id);
    audioPlayers.delete(interaction.guild.id);
    conn.destroy();
    await interaction.reply('Left voice channel.');
    return;
  }

  if (cmd === 'voice-say') {
    const text = interaction.options.getString('text', true);
    const conn = getVoiceConnection(interaction.guild.id);
    if (!conn) return interaction.reply('Join voice first with /voice-join.');
    try {
      await speakInCall(conn, interaction.guild.id, text);
      await interaction.reply('🔊 Speaking in call.');
    } catch (err) {
      await interaction.reply(`TTS playback error: ${err.message}`);
    }
    return;
  }
});

client.on(Events.MessageCreate, async (message) => {
  if (message.author.bot) return;
  if (!message.guild) return;
  if (guildId && message.guild.id !== guildId) return;
  if (!isAllowedTextChannel(message.channel.id)) return;
  if (!isAllowedUser(message.author.id)) return;

  const { cmd, args } = parseArgs(message.content);

  if (cmd === '!voice-status') {
    const conn = getVoiceConnection(message.guild.id);
    const state = listenState.get(message.guild.id);
    if (!conn) {
      await message.reply('Not connected to any voice channel.');
      return;
    }
    await message.reply(`Connected. State: **${conn.state.status}** | Listening: **${state?.enabled ? 'on' : 'off'}**`);
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

    if (!channel || !isAllowedVoiceChannel(channel.id)) {
      await message.reply('Voice channel is not allowlisted for this bot.');
      return;
    }

    try {
      await joinChannel(message, channel);
      await message.reply(`Joined **${channel.name}**.`);
    } catch (err) {
      await message.reply(`Failed to join: ${err.message}`);
    }
    return;
  }

  if (cmd === '!voice-listen') {
    const conn = getVoiceConnection(message.guild.id);
    if (!conn) {
      await message.reply('Join a voice channel first with `!voice-join`.');
      return;
    }

    const currently = listenState.get(message.guild.id);
    if (currently?.enabled) {
      await message.reply('Already listening.');
      return;
    }

    listenState.set(message.guild.id, {
      enabled: true,
      textChannelId: message.channel.id,
    });

    await startReceiver(conn, message.guild, message.channel);
    await message.reply('🎧 Listening started. Speak in voice channel and I will transcribe chunks here.');
    return;
  }

  if (cmd === '!voice-stop') {
    const st = listenState.get(message.guild.id);
    if (!st?.enabled) {
      await message.reply('Listening is not active.');
      return;
    }
    listenState.set(message.guild.id, { ...st, enabled: false });
    await message.reply('🛑 Listening stopped.');
    return;
  }

  if (cmd === '!voice-ask') {
    const prompt = args.join(' ').trim();
    if (!prompt) {
      await message.reply('Usage: `!voice-ask <text>`');
      return;
    }
    if (!routerUrl) {
      await message.reply('OPENCLAW_ROUTER_URL is not configured.');
      return;
    }
    try {
      const reply = await askOpenClawRouter({
        transcript: prompt,
        userId: message.author.id,
        userName: message.member?.displayName || message.author.username,
        guildId: message.guild.id,
        textChannelId: message.channel.id,
      });
      await message.reply(reply ? `🤖 ${clampReply(reply)}` : 'Router returned no reply payload.');
    } catch (err) {
      await message.reply(`Router error: ${err.message}`);
    }
    return;
  }

  if (cmd === '!voice-say') {
    const text = args.join(' ').trim();
    if (!text) {
      await message.reply('Usage: `!voice-say <text>`');
      return;
    }
    const conn = getVoiceConnection(message.guild.id);
    if (!conn) {
      await message.reply('Join voice first with `!voice-join`.');
      return;
    }
    try {
      await speakInCall(conn, message.guild.id, text);
      await message.reply('🔊 Speaking in call.');
    } catch (err) {
      await message.reply(`TTS playback error: ${err.message}`);
    }
    return;
  }

  if (cmd === '!voice-leave') {
    const conn = getVoiceConnection(message.guild.id);
    if (!conn) {
      await message.reply('I am not in a voice channel.');
      return;
    }
    listenState.delete(message.guild.id);
    audioPlayers.delete(message.guild.id);
    conn.destroy();
    await message.reply('Left voice channel.');
    return;
  }
});

process.on('uncaughtException', (err) => {
  log('uncaught_exception', { message: err.message });
});

process.on('unhandledRejection', (err) => {
  log('unhandled_rejection', { message: err?.message || String(err) });
});

client.login(token);
