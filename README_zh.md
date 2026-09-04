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

**在线演示：** [Cloud Run](https://vendorproof-web-qjv2kumm3q-as.a.run.app/)
· **演示视频：** [YouTube](https://youtu.be/z9RUGx1DMT8)
· **正式提交：** [Devpost](https://devpost.com/software/vendorproof)

---

## 寻找深圳的 AI 工作机会

作者目前正在寻找深圳的 AI 相关工作机会，重点关注腾讯等大型科技企业及金融机构的 **AI 投研产品、FDE 与 AI 咨询 / 解决方案岗位**。

兼具金融机构从业经历与 AI 产品实战，持续构建金融市场数据工具和多智能体系统，开源项目累计获得 **17K+ GitHub Stars**。

联系：[simonlin0423@gmail.com](mailto:simonlin0423@gmail.com)

---

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
2. SerpApi 为每个主张执行 Google Light 与 Google News 搜索；需求中写明的官网
   会直接绑定到对应供应商，未写官网时必须通过独立知识面板查询确认，避免同名
   公司证据混入。
3. Gemini 仅依据本次返回的证据生成结构化判断。
4. 系统逐字节核对引用，删除任何未在本次结果中出现的链接，并自动降低结论
   可信级别。
5. 任一搜索通道失败都会明确显示，不会静默当成“没有风险”。
6. Xano 保存需求和完整报告，返回快照编号及变化数量。

## 当前验证状态

- 391 项测试全部通过
- 全项目分支覆盖率 95.26%
- Ruff 静态检查通过
- Gemini 3.5 Flash 结构化输出冒烟测试通过
- Xano v5 已完成线上验收，快照 36–41 覆盖无变化、结论变化、官网变化和空报告
  新增主张
- Gemini、SerpApi、Xano 零流量候选版本真实联调通过，写入 Xano 快照 46
- 浏览器功能验收写入快照 47，正式生产冒烟测试写入快照 48
- Cloud Run 版本 `vendorproof-web-00003-qeg` 已承接 100% 生产流量
- 3 分 15 秒公开视频已发布，Devpost 项目 `1160958` 已正式提交
- SerpApi 与 Xano 两条现金赞助赛道均已选中

英文主文档包含完整架构、运行方法和安全约束，详见
[README.md](README.md)。当前开发门槛与下一步见 [NEXT.md](NEXT.md)。

## License

MIT，详见 [LICENSE](LICENSE)。

**作者：** Simon 林 · X [@linsizhen](https://x.com/linsizhen) · 邮箱：[simonlin0423@gmail.com](mailto:simonlin0423@gmail.com)

## 赞赏

<p align="center">
  <a href="https://buymeacoffee.com/simonlin1212"><img src="./assets/bmc-qr.png" width="180" alt="Buy Me a Coffee"></a>
</p>
