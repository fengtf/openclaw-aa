#!/usr/bin/env node

const fs = require('fs');
const TOML = require('@iarna/toml');
const { execSync } = require('child_process');

// 配置文件路径
const CONFIG_PATH = '/root/plugins/openclaw-plugin-askaway/Actr.toml';

// 读取环境变量
const RTC_REALM_ID = process.env.RTC_REALM_ID;
const RTC_SIGNALING_SERVER = process.env.RTC_SIGNALING_SERVER;
const RTC_TURN_SERVER = process.env.RTC_TURN_SERVER;
const RTC_STUN_SERVER = process.env.RTC_STUN_SERVER;

// 验证环境变量
const requiredEnvVars = {
  RTC_REALM_ID,
  RTC_SIGNALING_SERVER,
  RTC_TURN_SERVER,
  RTC_STUN_SERVER
};

const missingVars = Object.entries(requiredEnvVars)
  .filter(([key, value]) => !value)
  .map(([key]) => key);

if (missingVars.length > 0) {
  console.error('错误: 以下环境变量未设置:');
  missingVars.forEach(varName => console.error(`  - ${varName}`));
  process.exit(1);
}

try {
  // 读取并解析 TOML 文件
  console.log(`读取配置文件: ${CONFIG_PATH}`);
  const tomlContent = fs.readFileSync(CONFIG_PATH, 'utf8');
  const config = TOML.parse(tomlContent);

  // 更新配置
  console.log('更新配置项...');

  // 确保 system.deployment 存在
  if (!config.system) {
    config.system = {};
  }
  if (!config.system.deployment) {
    config.system.deployment = {};
  }

  // 更新 realm_id (转换为数字)
  const realmId = parseInt(RTC_REALM_ID, 10);
  if (isNaN(realmId)) {
    console.error(`错误: RTC_REALM_ID 必须是有效的数字，当前值: ${RTC_REALM_ID}`);
    process.exit(1);
  }
  config.system.deployment.realm_id = realmId;
  console.log(`  - realm_id = ${realmId}`);

  // 确保 system.signaling 存在
  if (!config.system.signaling) {
    config.system.signaling = {};
  }

  // 更新 signaling url
  config.system.signaling.url = RTC_SIGNALING_SERVER;
  console.log(`  - signaling.url = ${RTC_SIGNALING_SERVER}`);

  // 确保 system.webrtc 存在
  if (!config.system.webrtc) {
    config.system.webrtc = {};
  }

  // 更新 turn_urls (数组格式)
  config.system.webrtc.turn_urls = [RTC_TURN_SERVER];
  console.log(`  - webrtc.turn_urls = ["${RTC_TURN_SERVER}"]`);

  // 更新 stun_urls (数组格式)
  config.system.webrtc.stun_urls = [RTC_STUN_SERVER];
  console.log(`  - webrtc.stun_urls = ["${RTC_STUN_SERVER}"]`);

  // 将配置转换回 TOML 格式并写入文件
  console.log(`写入配置文件: ${CONFIG_PATH}`);
  const updatedToml = TOML.stringify(config);
  fs.writeFileSync(CONFIG_PATH, updatedToml, 'utf8');

  console.log('配置文件更新成功！');
  console.log('');

  // 安装插件
  console.log('开始安装 openclaw-plugin-askaway 插件...');
  try {
    const installCommand = 'openclaw plugins install /root/plugins/openclaw-plugin-askaway';
    console.log(`执行命令: ${installCommand}`);
    
    execSync(installCommand, { 
      stdio: 'inherit',  // 继承标准输入输出，实时显示命令输出
      encoding: 'utf8'
    });
    
    console.log('✓ 插件安装成功！');
    process.exit(0);
  } catch (installError) {
    console.error('✗ 插件安装失败:');
    console.error(installError.message);
    process.exit(1);
  }

} catch (error) {
  console.error('错误: 配置文件修改失败');
  console.error(error.message);
  if (error.stack) {
    console.error(error.stack);
  }
  process.exit(1);
}
