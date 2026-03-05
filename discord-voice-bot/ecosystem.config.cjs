module.exports = {
  apps: [
    {
      name: 'discord-voice-bot',
      script: 'src/index.js',
      cwd: '/Users/ericsysclaw/.openclaw/workspace/discord-voice-bot',
      watch: false,
      autorestart: true,
      max_restarts: 20,
      restart_delay: 3000,
      env_file: '.env',
      out_file: './logs/out.log',
      error_file: './logs/error.log',
      merge_logs: true,
      time: true,
    },
  ],
};
