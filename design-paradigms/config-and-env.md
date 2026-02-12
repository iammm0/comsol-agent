# 配置与环境变量范式

.env 分层、敏感信息存储与 env.example 约定，与具体业务无关。

## 1. 环境变量分层

- **首选 .env**：使用 `python-dotenv` 或类似在应用启动时加载 `.env`，便于本地与部署用同一套键名，且不把敏感值写进代码。
- **键命名**：按模块或功能前缀，如 `LLM_PROVIDER`、`OLLAMA_BASE_URL`、`DEEPSEEK_API_KEY`、`DATABASE_URL`、`LOG_LEVEL`，便于搜索与文档化。
- **布尔与数字**：用字符串（如 `true`/`false`、`0.7`），在代码里按需转为 bool/float；或约定 `1`/`0`、`yes`/`no` 并统一解析，避免多处解析逻辑不一致。

## 2. env.example 约定

- **提供 env.example**：列出所有支持的键及注释说明用途、可选值、示例。不包含真实密钥或敏感信息。
- **说明格式**：注释写清「当 XXX 时使用」「格式：…」「不设置时默认…」，便于新人与部署复制为 `.env` 后修改。
- **可选配置**：未使用的服务（如 ChromaDB）可在 env.example 中注释掉，并注明「当前未使用，仅用于 Docker Compose」等，避免误导。

## 3. 敏感信息与 keyring

- **原则**：API Key、密码等不写入 .env 提交到仓库；本地开发可 .env 且 .gitignore，生产建议用系统密钥环或密钥管理服务。
- **keyring**：使用 `keyring` 库，以「服务名 + 提供方」为键（如 `(KEYRING_SERVICE, provider)`）存取密码；提供 `get_api_key(provider)`、`set_api_key(provider, key)`、`delete_api_key(provider)`，以及可选的交互式 `configure_api_key(provider)`（用 getpass 输入，不回显）。
- **回退**：若 keyring 不可用或用户选择「用环境变量」，可约定如 `DEEPSEEK_API_KEY` 优先于 keyring，在代码里先读 env 再 keyring，并文档化顺序。

## 4. 配置状态与诊断

- **show_config_status()**：返回各 provider 是否已配置（如 `{ "deepseek": True, "ollama": False }`），便于 CLI 子命令或调试页展示「哪些已配置、哪些未配置」，而不暴露具体密钥。
- **日志**：避免在日志中打印完整 API Key；若需标识，仅打印前缀或掩码（如前 8 位 + `***`）。

## 5. 可复用要点小结

- 配置以 .env 为主，键名分层、注释完整；提供 env.example 且不含敏感信息。
- 敏感信息：keyring + 可选 env 回退；提供 get/set/delete/configure 与 status。
- 配置状态接口用于 CLI/调试，不暴露密钥；日志中不输出完整密钥。
