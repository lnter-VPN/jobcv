# jobcv — AI 简历优化 + ATS 关键词匹配

按目标岗位 JD 重写优化简历，并给出 ATS（简历筛选系统）关键词命中分。
提供 **命令行 / HTTP API / 网页版** 三种用法，核心算分零依赖、不联网、不花钱。

**后端无关**：默认 DeepSeek（便宜），也支持本地 Ollama 或任意 OpenAI 兼容接口——数据可不出本机。

> 🌐 **在线体验（临时 demo）**：<https://automotive-parade-eric-test.trycloudflare.com>
> 免费的「ATS 算分」无需任何 key 即可用；「AI 优化」需在页面里填你自己的 DeepSeek key（仅存在你浏览器本地，不上传服务器）。

---

## 安装

```bash
pip install jobcv            # 核心：CLI + ATS 算分，零依赖
pip install 'jobcv[zh]'      # +jieba，中文分词更准（推荐中文简历）
pip install 'jobcv[api]'     # +FastAPI/uvicorn，启用网页版
```

仓库自带 `examples/resume.txt`、`examples/jd.txt`，可直接试。

## 1. 命令行

```bash
# 只算 ATS 匹配分：不调模型、不花钱、不联网
jobcv score --resume examples/resume.txt --jd examples/jd.txt

# 加 --json，score / report / match 输出机器可读结果，方便脚本与 CI 集成
jobcv score --resume resume.txt --jd jd.txt --json

# 按 JD 优化简历（默认 DeepSeek）
export DEEPSEEK_API_KEY=sk-xxx
jobcv polish --resume resume.txt --jd jd.txt --out resume.opt.txt

# 用本地 Ollama，数据完全不出本机
jobcv polish --resume resume.txt --jd jd.txt --backend ollama --model qwen2.5:3b

# 任意 OpenAI 兼容接口
jobcv polish --resume resume.txt --jd jd.txt \
    --base-url http://x/v1 --model your-model --api-key xxx
```

`polish` 会在优化前后各算一次 ATS 分，直接告诉你提升了多少。

## 2. 网页版

```bash
pip install 'jobcv[api]'
jobcv serve                  # 打开 http://127.0.0.1:8000
```

左侧贴 JD 和简历，一键「算 ATS 分（免费）」或「AI 优化简历」；右侧实时显示
分数环、命中/缺失关键词、优化前后对比和优化后正文。API key 仅存浏览器本地。

## 3. HTTP API

`jobcv serve` 同时提供 JSON 接口，可嵌进自己的系统：

```bash
# 算分（免费、纯本地）
curl -X POST http://127.0.0.1:8000/api/score \
  -H 'Content-Type: application/json' \
  -d '{"resume":"...", "jd":"..."}'
# -> {"score":60.0,"matched":[...],"missing":[...],"total":5}

# 优化（调用 LLM）
curl -X POST http://127.0.0.1:8000/api/polish \
  -H 'Content-Type: application/json' \
  -d '{"resume":"...", "jd":"...", "backend":"deepseek", "api_key":"sk-xxx"}'
```

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/health`   | 健康检查 |
| GET  | `/api/backends` | 可用后端列表 |
| POST | `/api/score`    | ATS 关键词匹配分（不调用 LLM） |
| POST | `/api/polish`   | 按 JD 优化简历（调用 LLM） |

## ATS 算分怎么算的

纯 stdlib、完全可测，比朴素 bag-of-words 更准：

- **同义词/技能词典** —— `k8s`=`kubernetes`、`js`=`javascript`、`机器学习`=`ML`，跨中英文也能对上。
- **词频加权** —— JD 反复强调的关键词权重更高，分数更贴近岗位真实侧重。
- **英文按词边界匹配** —— `go` 不再误命中 `good`，`ai` 不再误命中 `training`。
- **中文分词** —— 装了 `jieba`（`jobcv[zh]`）更准，没装则退化为 n-gram。

## 后端对比

| 后端 | 地址 | 适合 |
|------|------|------|
| DeepSeek（默认） | api.deepseek.com | 大多数人，¥几分钱/次 |
| 本地 Ollama | localhost:11434 | 有显卡 / 想离线 / 数据敏感 |
| 自定义 | 任意 OpenAI 兼容 | 折腾党 |

> 优化时严禁编造经历，只重组表达、量化成果、自然融入 JD 关键词。

## 开发

```bash
pip install -e '.[dev]'
pytest                       # 运行测试
python -m build              # 打包 wheel/sdist
```

MIT License.
</content>
</invoke>
