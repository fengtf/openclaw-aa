#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const os = require('os');

const CUSTOM_MODEL_PROVIDER = process.env.CUSTOM_MODEL_PROVIDER;
const CUSTOM_MODEL_BASE_PATH = process.env.CUSTOM_MODEL_BASE_PATH;
const CUSTOM_MODEL_API_KEY = process.env.CUSTOM_MODEL_API_KEY;
const CUSTOM_MODEL_NAME = process.env.CUSTOM_MODEL_NAME;

// 验证必需的环境变量
const missing = [];
if (!CUSTOM_MODEL_PROVIDER) missing.push('CUSTOM_MODEL_PROVIDER');
if (!CUSTOM_MODEL_BASE_PATH) missing.push('CUSTOM_MODEL_BASE_PATH');
if (!CUSTOM_MODEL_API_KEY) missing.push('CUSTOM_MODEL_API_KEY');
if (!CUSTOM_MODEL_NAME) missing.push('CUSTOM_MODEL_NAME');

if (missing.length > 0) {
  console.error('错误: 以下环境变量未设置:');
  missing.forEach(v => console.error(`  - ${v}`));
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

// 确保必要的嵌套结构存在
if (!config.agents) config.agents = {};
if (!config.agents.defaults) config.agents.defaults = {};
if (!config.agents.defaults.models) config.agents.defaults.models = {};
if (!config.agents.defaults.model) config.agents.defaults.model = {};
if (!config.models) config.models = {};
if (!config.models.providers) config.models.providers = {};

const modelFullId = `${CUSTOM_MODEL_PROVIDER}/${CUSTOM_MODEL_NAME}`;

// 更新 agents.defaults 使用自定义模型
config.agents.defaults.model.primary = modelFullId;
config.agents.defaults.models[modelFullId] = { alias: CUSTOM_MODEL_NAME };

// 更新 models.providers 中的自定义 provider 配置
config.models.mode = 'merge';
config.models.providers[CUSTOM_MODEL_PROVIDER] = {
  baseUrl: CUSTOM_MODEL_BASE_PATH,
  apiKey: CUSTOM_MODEL_API_KEY,
  api: 'openai-completions',
  models: [
    { id: CUSTOM_MODEL_NAME, name: CUSTOM_MODEL_NAME }
  ]
};

// 写回配置文件
const dir = path.dirname(CONFIG_PATH);
if (!fs.existsSync(dir)) {
  fs.mkdirSync(dir, { recursive: true });
}
fs.writeFileSync(CONFIG_PATH, JSON.stringify(config, null, 2), 'utf8');

console.log('✓ openclaw.json 配置更新成功');
console.log(`  provider: ${CUSTOM_MODEL_PROVIDER}`);
console.log(`  baseUrl: ${CUSTOM_MODEL_BASE_PATH}`);
console.log(`  model: ${modelFullId}`);
process.exit(0);
