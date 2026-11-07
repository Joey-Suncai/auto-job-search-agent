# Dashboard English display — spec (2026-11-05, JSA-180)

The dashboard keeps the store's Chinese values and shows them in English through `en(text)`.
1. The five eligibility values map exactly: 可投 → "Eligible", 待核实 → "To verify", 不可投 → "Not eligible",
   已关闭 → "Closed", 重复 → "Duplicate" (surrounding spaces ignored).
2. Any other text (eligibility reasons written by the checker, e-mail status, action notes) comes out with NO Chinese
   characters left, when it is built from these phrases (joined by "；" and with "（…）" asides): 读到完整 JD，未发现限制 ·
   读不到 JD（需要登录或网站不支持），申请前人工核实 · 不提供签证担保 · 与 J<5 digits> 是同一个岗位 · 岗位已下线 ·
   要求美国公民/绿卡、安全许可或出口管制身份 · 不是暑期实习（冬/春/秋季或 co-op） · 毕业时间要求不含 <yyyy> 年 <m> 月 ·
   要求 <n> 年以上工作经验 · 只招本科（大三/大四） · 毕业时间符合 · JD 写的是本科在读 · 网站标注的截止日期已过，可能已关闭，申请前确认 ·
   不在美国 · 只招博士 · 实习期超过 <n> 周 / 多学期 · 学期中要兼职 · 只招 MBA · 明确提供担保 · 担保说法前后矛盾 · JD 太短或读不到 ·
   （<yyyy-mm-dd> 读到的 JD） · （<yyyy-mm-dd> 读不到） · 暂无回应 · 等结果 · 请确认（Claude 不确定）：<English text>.
3. Every J-number (J followed by 5 digits), every date (yyyy-mm-dd), every number of years / weeks, and every run of
   English (ASCII) words in the input still appears, unchanged, in the output.
4. null / undefined come back unchanged; plain English text comes back unchanged.
