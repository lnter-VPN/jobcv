# jobcv — AI 简历优化 + ATS 关键词匹配

按目标岗位 JD 重写优化简历，并给出 ATS（简历筛选系统）关键词命中分。
**后端无关**：默认用 DeepSeek，也支持本地 Ollama 或任意 OpenAI 兼容接口——数据可不出本机。

## 安装

```bash
pip install jobcv          # 核心零依赖
pip install jobcv[zh]      # +jieba，中文分词更准（推荐中文简历）
```

## 用法

仓库自带 `examples/resume.txt`、`examples/jd.txt` 可直接试。

```bash
# 1) 只看 ATS 匹配分，不花一分钱、不调模型
jobcv score --resume examples/resume.txt --jd examples/jd.txt

# 2) 按 JD 优化简历（默认 DeepSeek，最便宜）
export DEEPSEEK_API_KEY=sk-xxx
jobcv polish --resume resume.txt --jd jd.txt --out resume.opt.txt

# 3) 用本地 Ollama，数据完全不出本机
jobcv polish --resume resume.txt --jd jd.txt \
    --backend ollama --model qwen2.5:3b

# 4) 任意 OpenAI 兼容接口
jobcv polish --resume resume.txt --jd jd.txt \
    --base-url http://x/v1 --model your-model --api-key xxx
```

`polish` 会在优化前后各算一次 ATS 分，直接告诉你提升了多少。

## 后端对比

| 后端 | 地址 | 适合 |
|------|------|------|
| DeepSeek（默认） | api.deepseek.com | 大多数人，¥几分钱/次 |
| 本地 Ollama | localhost:11434 | 有显卡 / 想离线 / 数据敏感 |
| 自定义 | 任意 OpenAI 兼容 | 折腾党 |

> 优化时严禁编造经历，只重组表达、量化成果、自然融入 JD 关键词。

MIT License.
