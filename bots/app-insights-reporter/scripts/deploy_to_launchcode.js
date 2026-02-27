#!/usr/bin/env node
/**
 * Deploy LoA App Insights Reporter to LaunchCode
 *
 * Usage:
 *   cd bots/app-insights-reporter
 *   node scripts/deploy_to_launchcode.js | ~/.launchcode/scripts/api.js
 *
 * This script reads all source files from disk, escapes them for JavaScript,
 * and outputs the api.js code to create/update the job.
 */
const fs = require('fs');
const path = require('path');

const botDir = path.resolve(__dirname, '..');

// Read all source files
const files = {
  runSh: fs.readFileSync(path.join(botDir, 'scripts/run.sh'), 'utf8'),
  fetchInsights: fs.readFileSync(path.join(botDir, 'src/fetch_insights.py'), 'utf8'),
  fetchBusinessMetrics: fs.readFileSync(path.join(botDir, 'src/fetch_business_metrics.py'), 'utf8'),
  formatReport: fs.readFileSync(path.join(botDir, 'src/format_report.py'), 'utf8'),
  postToSlack: fs.readFileSync(path.join(botDir, 'src/post_to_slack.py'), 'utf8'),
  getDateRange: fs.readFileSync(path.join(botDir, 'src/get_date_range.py'), 'utf8'),
  azLoginPlaywright: fs.readFileSync(path.join(botDir, 'src/az_login_playwright.py'), 'utf8'),
  vpnConfig: fs.readFileSync(path.join(botDir, '../../vpn.ovpn'), 'utf8'),
};

// Read env file for default values
const envVars = {};
try {
  const envContent = fs.readFileSync(path.join(botDir, '../../.env'), 'utf8');
  for (const line of envContent.split('\n')) {
    const trimmed = line.trim();
    if (trimmed && !trimmed.startsWith('#')) {
      const eqIdx = trimmed.indexOf('=');
      if (eqIdx > 0) {
        envVars[trimmed.substring(0, eqIdx)] = trimmed.substring(eqIdx + 1);
      }
    }
  }
} catch (e) {
  console.error('Error: Could not read root .env — run from the repo root or bots/app-insights-reporter');
  process.exit(1);
}

const required = ['AZURE_APP_INSIGHTS_WORKSPACE_ID', 'AZURE_ACCESS_TOKEN', 'SLACK_BOT_TOKEN', 'SLACK_CHANNEL', 'REDSHIFT_HOST', 'REDSHIFT_DATABASE', 'REDSHIFT_USER', 'REDSHIFT_PASSWORD', 'MYSQL_HOST', 'MYSQL_DATABASE', 'MYSQL_USER', 'MYSQL_PASSWORD'];
const missing = required.filter(k => !envVars[k]);
if (missing.length) {
  console.error(`Missing required .env vars: ${missing.join(', ')}`);
  process.exit(1);
}

// Dockerfile content
const dockerfile = `FROM public.ecr.aws/docker/library/python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \\
    bash \\
    curl \\
    ca-certificates \\
    git \\
    openvpn \\
    iproute2 \\
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \\
    slack-sdk \\
    requests \\
    python-dateutil \\
    psycopg2-binary \\
    mysql-connector-python \\
    azure-cli \\
    playwright
RUN playwright install --with-deps chromium

WORKDIR /app
SHELL ["/bin/bash", "-c"]
CMD ["bash", "/app/run.sh"]
`;

// Build the job config as a JSON-safe object
const jobConfig = {
  name: 'LoA Application Insights Summary',
  slug: 'loa-app-insights-summary',
  description: 'Daily health report for LoA application - fetches Azure App Insights, Redshift, and MySQL metrics, then posts a formatted summary to Slack.',
  config: {
    dockerfile: dockerfile,
    cpu: 512,
    memory: 1024,
    script: 'bash /app/run.sh',
    env_vars: [
      { key: 'AZURE_APP_INSIGHTS_WORKSPACE_ID', value: envVars.AZURE_APP_INSIGHTS_WORKSPACE_ID, secret: false },
      { key: 'AZURE_ACCESS_TOKEN', value: envVars.AZURE_ACCESS_TOKEN, secret: true },
      { key: 'SLACK_BOT_TOKEN', value: envVars.SLACK_BOT_TOKEN, secret: true },
      { key: 'SLACK_CHANNEL', value: envVars.SLACK_CHANNEL, secret: false },
      { key: 'REDSHIFT_HOST', value: envVars.REDSHIFT_HOST, secret: false },
      { key: 'REDSHIFT_PORT', value: envVars.REDSHIFT_PORT || '5439', secret: false },
      { key: 'REDSHIFT_DATABASE', value: envVars.REDSHIFT_DATABASE, secret: false },
      { key: 'REDSHIFT_USER', value: envVars.REDSHIFT_USER, secret: false },
      { key: 'REDSHIFT_PASSWORD', value: envVars.REDSHIFT_PASSWORD, secret: true },
      { key: 'MYSQL_HOST', value: envVars.MYSQL_HOST, secret: false },
      { key: 'MYSQL_PORT', value: envVars.MYSQL_PORT || '3306', secret: false },
      { key: 'MYSQL_DATABASE', value: envVars.MYSQL_DATABASE, secret: false },
      { key: 'MYSQL_USER', value: envVars.MYSQL_USER, secret: false },
      { key: 'MYSQL_PASSWORD', value: envVars.MYSQL_PASSWORD, secret: true },
      // OpenVPN
      { key: 'OPENVPN_HOST', value: '34.237.171.105', secret: false },
      { key: 'OPENVPN_USER', value: 'pmoran', secret: false },
      { key: 'OPENVPN_PASS', value: envVars.OPENVPN_PASS, secret: true },
      // Azure CLI login (one-time, via Playwright + Okta)
      { key: 'AZURE_EMAIL', value: envVars.AZURE_EMAIL, secret: true },
      { key: 'AZURE_PASSWORD', value: envVars.AZURE_PASSWORD, secret: true },
      { key: 'OKTA_TOTP_CODE', value: '', secret: true },
    ],
    files: [
      { path: '/app/run.sh', content: files.runSh, mode: '755' },
      { path: '/app/fetch_insights.py', content: files.fetchInsights, mode: '755' },
      { path: '/app/fetch_business_metrics.py', content: files.fetchBusinessMetrics, mode: '755' },
      { path: '/app/format_report.py', content: files.formatReport, mode: '755' },
      { path: '/app/post_to_slack.py', content: files.postToSlack, mode: '755' },
      { path: '/app/get_date_range.py', content: files.getDateRange, mode: '755' },
      { path: '/app/az_login_playwright.py', content: files.azLoginPlaywright, mode: '755' },
      { path: '/app/vpn.ovpn', content: files.vpnConfig, mode: '600' },
    ],
  },
  schedules: [
    {
      cron_expression: '30 8 * * 1-5',
      timezone: 'America/New_York',
      enabled: true,
    },
  ],
  enabled: true,
};

// Output the api.js code using JSON.stringify for safe escaping
const configJson = JSON.stringify(jobConfig, null, 2);

console.log(`
const jobConfig = ${configJson};

const job = await api.jobs.create(jobConfig);

console.log('Job created successfully!');
console.log('  ID:', job.id);
console.log('  Slug:', job.slug);
console.log('  Name:', job.name);
console.log('  Enabled:', job.enabled);
if (job.schedules && job.schedules.length > 0) {
  console.log('  Schedule:', job.schedules[0].cron_expression, job.schedules[0].timezone);
}
console.log('');
console.log('Next steps:');
console.log('  1. Trigger a manual run to test: node scripts/trigger_launchcode.js | ~/.launchcode/scripts/api.js');
console.log('  2. Check logs in LaunchCode UI');
`);
