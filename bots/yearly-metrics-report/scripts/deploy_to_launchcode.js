#!/usr/bin/env node
/**
 * Deploy Yearly Metrics Report to LaunchCode
 *
 * Usage:
 *   cd bots/yearly-metrics-report
 *   node scripts/deploy_to_launchcode.js | ~/.launchcode/scripts/api.js
 */
const fs = require('fs');
const path = require('path');

const botDir = path.resolve(__dirname, '..');

const files = {
  runSh: fs.readFileSync(path.join(botDir, 'scripts/run.sh'), 'utf8'),
  fetchYearly: fs.readFileSync(path.join(botDir, 'src/fetch_yearly_metrics.py'), 'utf8'),
  postToSlack: fs.readFileSync(path.join(botDir, 'src/post_yearly_to_slack.py'), 'utf8'),
  vpnConfig: fs.readFileSync(path.join(botDir, '../../vpn.ovpn'), 'utf8'),
};

// Read root .env
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
  console.error('Error: Could not read root .env — run from the repo root or bots/yearly-metrics-report');
  process.exit(1);
}

const required = ['SLACK_BOT_TOKEN', 'YEARLY_METRICS_SLACK_CHANNEL', 'REDSHIFT_HOST', 'REDSHIFT_DATABASE', 'REDSHIFT_USER', 'REDSHIFT_PASSWORD', 'MYSQL_HOST', 'MYSQL_DATABASE', 'MYSQL_USER', 'MYSQL_PASSWORD'];
const missing = required.filter(k => !envVars[k]);
if (missing.length) {
  console.error(`Missing required .env vars: ${missing.join(', ')}`);
  process.exit(1);
}

const dockerfile = `FROM public.ecr.aws/docker/library/python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \\
    bash curl ca-certificates git \\
    openvpn iproute2 \\
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir slack-sdk requests psycopg2-binary mysql-connector-python
WORKDIR /app
SHELL ["/bin/bash", "-c"]
CMD ["bash", "/app/run.sh"]
`;

const jobConfig = {
  name: 'Yearly Metrics Report',
  slug: 'yearly-metrics-report',
  description: `Yearly Business Metrics Report — posts annual offers & upsells summary with monthly/quarterly breakdowns, trend charts, highlights, and weekend vs weekday analysis to Slack.

HOW TO CONFIGURE:
  REPORT_YEAR — Year to generate report for (e.g. 2025). Leave empty for current year.

EXAMPLES:
  Year 2025: REPORT_YEAR=2025
  Year 2024: REPORT_YEAR=2024
  Current year: Leave empty.

Set the value above in the Environment Variables section, then trigger manually.`,
  config: {
    dockerfile,
    cpu: 512,
    memory: 1024,
    script: 'bash /app/run.sh',
    env_vars: [
      { key: 'SLACK_BOT_TOKEN', value: envVars.SLACK_BOT_TOKEN, secret: true },
      { key: 'YEARLY_METRICS_SLACK_CHANNEL', value: envVars.YEARLY_METRICS_SLACK_CHANNEL, secret: false },
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
      // Parameters — override these when triggering manually
      { key: 'REPORT_YEAR', value: '', secret: false },
    ],
    files: [
      { path: '/app/run.sh', content: files.runSh, mode: '755' },
      { path: '/app/fetch_yearly_metrics.py', content: files.fetchYearly, mode: '755' },
      { path: '/app/post_yearly_to_slack.py', content: files.postToSlack, mode: '755' },
      { path: '/app/vpn.ovpn', content: files.vpnConfig, mode: '600' },
    ],
  },
  schedules: [
    {
      cron_expression: '0 0 1 1 *',
      timezone: 'America/New_York',
      enabled: false,
    },
  ],
  enabled: true,
};

const configJson = JSON.stringify(jobConfig, null, 2);

console.log(`
const jobConfig = ${configJson};

const job = await api.jobs.create(jobConfig);

console.log('Job created!');
console.log('  ID:', job.id);
console.log('  Slug:', job.slug);
console.log('');
console.log('To trigger a run for 2025:');
console.log('  Update REPORT_YEAR=2025 in LaunchCode UI, then trigger manually');
console.log('  Or use: api.jobs.run("yearly-metrics-report")');
`);
