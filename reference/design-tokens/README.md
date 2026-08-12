# Tyndall Labs 设计 token（视觉参考，非运行时依赖）

从 claude.ai/design 的 **Tyndall Labs** 项目同步下来的设计系统片段：clay 陶土橙 + kraft
暖中性 + 象牙底。原先是 `/markets` 那个 React 仪表盘的运行时资源，该页面删除后这些文件
不再被任何代码加载，移到这里纯作视觉参考。

- `tokens/` — 颜色、字体、排版、间距、阴影的 CSS 变量
- `styles.css` — 汇总 import 上面五个 token 文件
- `assets/` — 品牌标记与字标 SVG

**代码里的实际调色板不在这儿**：报告与控制台的配色、字体栈是内联在
`quant_agent/market_intel.py` 的 `_CSS_PALETTE_LIGHT` / `_CSS_PALETTE_DARK` /
`_CSS_FONTS_*` 里（artifact 要求零外链，不能 @import）。改视觉时以那边为准，这里用来
核对色值和层级关系。
