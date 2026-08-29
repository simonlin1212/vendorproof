<p align="center"><a href="README.md">English</a> | <b>简体中文</b></p>

<h1 align="center">VendorProof</h1>

<p align="center">
  <b>用实时证据做供应商决策，不再依赖过期表格。</b><br>
  实时网络研究 · 精确引用 · 风险信号 · 历史快照
</p>

---

![VendorProof 采购需求界面](assets/screenshots/vendorproof-cloud-run.png)

VendorProof 是面向小团队的证据优先采购助手。输入软件或供应商需求后，
系统会通过 SerpApi 获取当前 Google 网页和新闻结果，再由 Gemini 判断关键
主张是已证实、已变化、存在冲突还是证据不足。AI 只能引用本次搜索真实返回
的原始链接；Xano 保存需求与证据快照，后续刷新时可以看到发生了什么变化。

这是为
[DevNetwork API + Cloud + AI Hackathon 2026](https://api-cloud-ai-hackathon-2026.devpost.com/)
SerpApi 与 Xano 现金赛道独立开发的项目。

## 解决的问题

供应商对比往往保存在表格里，但价格、套餐限制、集成能力和服务可靠性会不断
变化。普通 AI 回答如果隐藏不确定性或编造引用，只会放大风险。

VendorProof 把一次性表格变成可重复核验的证据档案：

- 对每个关键主张进行实时网页与新闻搜索；
- 展示精确、可点击的来源链接；
- 明确显示矛盾、缺失和部分搜索失败；
- 给出保守的“可发布 / 需复核 / 暂停”状态；
- 保存历史快照，支持后续追踪变化。

## 工作流程

1. Gemini 从采购需求中提取最多五个可核验主张。
2. SerpApi 为每个主张执行 Google Light 与 Google News 搜索。
3. Gemini 仅依据本次返回的证据生成结构化判断。
4. 系统逐字节核对引用，删除任何未在本次结果中出现的链接，并自动降低结论
   可信级别。
5. 任一搜索通道失败都会明确显示，不会静默当成“没有风险”。
6. Xano 保存需求和完整报告，返回快照编号及变化数量。

## 当前验证状态

- 40 项测试全部通过
- 全项目覆盖率 94%
- Ruff 静态检查通过
- Gemini 3.5 Flash 结构化输出冒烟测试通过
- 独立代码审查已收敛为无可执行问题
- SerpApi 与 Xano 真实联调等待账号登录

英文主文档包含完整架构、运行方法和安全约束，详见
[README.md](README.md)。当前开发门槛与下一步见 [NEXT.md](NEXT.md)。

## License

MIT，详见 [LICENSE](LICENSE)。

**作者：** Simon 林 · X [@linsizhen](https://x.com/linsizhen) · 邮箱：[simonlin0423@gmail.com](mailto:simonlin0423@gmail.com)

## 赞赏

<p align="center">
  <a href="https://buymeacoffee.com/simonlin1212"><img src="./assets/bmc-qr.png" width="180" alt="Buy Me a Coffee"></a>
</p>
