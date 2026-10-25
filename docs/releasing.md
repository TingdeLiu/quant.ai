# 发版

打一个 `vX.Y.Z` 的 tag 就发到 PyPI。凭据走 PyPI 的 trusted publishing（OIDC），
**仓库里不存任何 token**，GitHub 用一次性身份凭证向 PyPI 证明「这个 workflow 确实
来自这个仓库」。

## 一次性配置

### 1. 在 PyPI 登记 pending publisher

项目还没发布过，所以要用 "pending publisher"（已发布的项目则在项目设置里加）。
打开 <https://pypi.org/manage/account/publishing/>，填：

| 字段 | 值 |
| --- | --- |
| PyPI Project Name | `quant-ai` |
| Owner | `TingdeLiu` |
| Repository name | `quant.ai` |
| Workflow name | `release.yml` |
| Environment name | `pypi` |

四项必须和 [release.yml](../.github/workflows/release.yml) 完全一致，否则 PyPI 会拒绝这次上传。

### 2. 建 GitHub environment

仓库 Settings → Environments → New environment，名字 `pypi`。

建议给它加 **required reviewers**（你自己）：这样每次 tag 推上去，发版会停在
publish 这一步等你点一下。构建和检查照常跑完，但不会自动上传。

## 每次发版

```bash
# 1. 改版本号（唯一事实源）
#    quant_agent/__init__.py 里的 __version__

# 2. 本地预检（和 CI 跑的是同一套）
python -m build && python scripts/check_dist.py dist/*

# 3. 提交并打 tag —— tag 必须等于 __version__，否则 workflow 会拒绝
git commit -am "release: 0.2.0"
git tag v0.2.0
git push && git push --tags
```

workflow 会按顺序跑 ruff → pytest → tag 与 `__version__` 核对 → 构建 → 产物检查，
全过了才进 publish。因为 **PyPI 的版本号不可重用** —— 发错一次就只能废掉那个号，
所以宁可把检查都堆在上传之前。

## 产物检查在拦什么

[scripts/check_dist.py](../scripts/check_dist.py) 盯两件最难补救的事：

1. **默认配置必须随包分发**。`configs/` 以 `quant_agent.templates` 的名字打进 wheel
   （见 pyproject 的 `package-dir`），缺了的话用户 `pip install` 完找不到配置。
2. **个人文件绝不能进包**。`my.yaml` / `my_universe.csv` / `profile.json` 是本地
   gitignore 的自选股与偏好，按 `*.yaml` / `*.csv` 的 glob 会被误收。排除规则在
   pyproject 的 `exclude-package-data`，名单的唯一事实源是 `quant_agent.paths.PRIVATE_NAMES`。
   发到 PyPI 的包是撤不回来的，所以这条有负向测试盯着。

## 想先演练

先登记一个 TestPyPI 的 pending publisher（<https://test.pypi.org/manage/account/publishing/>，
Environment 填 `testpypi`），复制一份 workflow，给 publish 步骤加：

```yaml
with:
  repository-url: https://test.pypi.org/legacy/
```
