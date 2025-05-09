module.exports = {
  apps: [
    {
      name: 'finance-bot',
      script: 'main.py',
      interpreter: 'python3',
      watch: false,
      env: {
        // Можно добавить переменные окружения, если нужно
      }
    },
    {
      name: 'import_data_to_bot',
      script: 'import_data_to_bot.py',
      interpreter: 'python3',
      watch: false,
      env: {
        // Здесь можно указать переменные окружения, если нужно
      }
    }
  ]
};
