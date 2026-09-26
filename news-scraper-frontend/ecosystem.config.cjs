module.exports = {
  apps: [
    {
      name: "news-scraper-frontend",
      script: "node_modules/vite/bin/vite.js",
      args: ["--host"],
      cwd: __dirname,
      autorestart: true,
      max_restarts: 50,
      restart_delay: 5000,
      windowsHide: true,
    },
  ],
};
