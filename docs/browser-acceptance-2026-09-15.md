# Browser Acceptance Evidence

This record captures the local Playwright smoke scenarios run against the fresh Python 3.11 clone on 2026-09-15. The browser session used the local frontend at `http://127.0.0.1:5500/`; injected fixtures were used only to exercise deterministic failure and security boundaries. The committed smoke suite also runs in GitHub Actions against the Docker Compose stack.

## Scenarios

| Scenario | Result | Observed evidence |
|---|---|---|
| XSS text rendering | Passed | Product/store payloads containing `<img>` and `<svg>` did not execute (`window.__xss=0`); no injected `img` or `svg` elements were created; tooltip text remained visible as text |
| Partial forecast coverage | Passed | The page showed `预测覆盖不完整：成功 1/2，失败 1 项`; save remained disabled and loading settled |
| Timeout and retry | Passed | Timeout showed `数据加载失败: 请求超时: /dashboard`; refresh became available; the next successful response cleared the error and updated the dashboard |
| API 500 | Passed | The page showed `数据加载失败: 模拟 API 故障`; refresh remained available and loading settled |
| Empty data | Passed | The page showed `当前筛选范围暂无可展示数据`; loading settled and the browser console had no unexpected messages |
| Delayed scope change | Passed | The final state showed `当前范围：#2 P2 · 全部门店`, timestamp `scope-2`, and no visible error; the older response did not overwrite the newer scope |
| Trend chart band | Passed | The real ECharts instance rendered 5 line series; `情景范围下界` and `情景范围` each contained 120 points, used `stack=scenario-range`, and the upper band data was positive |
| Committed Playwright smoke in GitHub Actions | Passed | Final run [35061473771](https://github.com/Caser-86/sales-forecast-dashboard/actions/runs/35061473771) passed both committed Chromium cases: save/idempotent recovery plus export, and narrow-viewport reachability |
| Real Google Chrome 200% zoom | Passed | `npm run test:e2e:zoom` used an isolated Chrome profile with actual browser zoom; `devicePixelRatio=2`, CSS viewport `640x450`, refresh/plan/save were visible in-viewport, product `#1` was selected, save succeeded, export was reachable, and page errors were empty. See [JSON output](evidence/browser-zoom-200-2026-09-16.json) and [screenshot](evidence/browser-zoom-200-2026-09-16.png) |

## Representative outputs

```text
XSS: {"xss":0,"rawImg":false,"rawSvg":false,"injectedImgElements":0,"injectedSvgElements":0,"tooltipText":true}
Partial: {"errorVisible":true,"saveDisabled":true,"loadingHidden":true}
Timeout/retry: {"timeoutState":{"errorVisible":true,"refreshDisabled":false},"retryState":{"errorHidden":true,"refreshDisabled":false},"dashboardCalls":2}
API 500: {"errorVisible":true,"refreshDisabled":false,"loadingHidden":true}
Empty: {"emptyVisible":true,"loadingHidden":true}
Delayed scope: {"scope":"当前范围：#2 P2 · 全部门店","updated":"数据更新时间：scope-2","errorVisible":false}
Trend: [{"name":"情景范围下界","points":120,"stack":"scenario-range"},{"name":"情景范围","points":120,"stack":"scenario-range"}]
```

The exact 200% target-browser evidence is now proven for Google Chrome through the committed local verifier and attached output. Docker, fixed 4-core/8GB performance, and dependency-audit evidence are recorded separately.
