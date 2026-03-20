#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const os = require('os');

const SEARCH_PROVIDER = process.env.SEARCH_PROVIDER;
const SEARCH_API_KEY = process.env.SEARCH_API_KEY;
const SEARCH_BASE_URL = process.env.SEARCH_BASE_URL;

if (!SEARCH_PROVIDER) {
  console.error('错误: 环境变量 SEARCH_PROVIDER 未设置');
  process.exit(1);
}

if (!SEARCH_API_KEY) {
  console.error('错误: 环境变量 SEARCH_API_KEY 未设置');
  process.exit(1);
}

const CONFIG_PATH = path.join(os.homedir(), '.openclaw', 'openclaw.json');
console.log(`读取配置文件: ${CONFIG_PATH}`);

let config = {};
if (fs.existsSync(CONFIG_PATH)) {
  const content = fs.readFileSync(CONFIG_PATH, 'utf8');
  config = JSON.parse(content);
} else {
  console.log('配置文件不存在，将创建新文件');
}

if (!config.tools) config.tools = {};
if (!config.tools.web) config.tools.web = {};
if (!config.tools.web.search) config.tools.web.search = {};

config.tools.profile = 'coding';
config.tools.web.search.enabled = true;
config.tools.web.search.provider = SEARCH_PROVIDER;
config.tools.web.search[SEARCH_PROVIDER] = {
  apiKey: SEARCH_API_KEY,
};

if (SEARCH_BASE_URL) {
  config.tools.web.search[SEARCH_PROVIDER].baseUrl = SEARCH_BASE_URL;
}

const dir = path.dirname(CONFIG_PATH);
if (!fs.existsSync(dir)) {
  fs.mkdirSync(dir, { recursive: true });
}
fs.writeFileSync(CONFIG_PATH, JSON.stringify(config, null, 2), 'utf8');

console.log('✓ openclaw.json 搜索配置更新成功');
console.log(`  provider: ${SEARCH_PROVIDER}`);
process.exit(0);
