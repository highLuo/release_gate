# release-gate

[![release-gate](https://github.com/highLuo/release_gate/actions/workflows/release-gate.yml/badge.svg)](https://github.com/highLuo/release_gate/actions/workflows/release-gate.yml)

发布前双闸：一条命令同时把住「代码别漏密钥」和「文案别踩合规红线」。

- **toksentry** —— 扫描代码/仓库里的密钥、令牌、私钥泄露（正则 + 香农熵）
- **fin-compliance** —— 扫描金融营销/投教/研报类文案，标出收益承诺、荐股暗示、夸大宣传、引流话术、AI 生成未标识

两个子扫描器都是**纯标准库、零依赖**，可离线运行。release-gate 把它们串起来，给出统一报告和退出码，直接卡 CI / pre-commit / 私有化交付。

## 为什么是双闸

单独做密钥扫描，金融类文案里的「保本保收益」「老师带单」就漏过去了；单独做内容合规，代码仓库里硬编码的 AWS Key 又没人管。发布前的事故往往两类都有，所以干脆一次查全。

## 安装

不需要 pip。把 `release_gate` 目录连同 `toksentry`、`fin-compliance` 两个兄弟目录放在一起即可（默认相对路径查找）：

```
projects/
├── toksentry/          (子扫描器 A)
├── fin-compliance/     (子扫描器 B)
└── release_gate/       (本目录)
    └── release_gate.py
```

需要 Python 3.8+，没有任何第三方包。

## 用法

扫同一个仓库（代码和内容都在里面）：

```bash
python release_gate.py /path/to/repo
```

代码和内容分开放：

```bash
python release_gate.py --code-dir ./src --content-dir ./docs
```

只在内容达到某个严重级别时才失败（默认 high；none=只报告不拦截）：

```bash
python release_gate.py /path/to/repo --fail-on medium
```

输出 JSON（方便接别的工具）：

```bash
python release_gate.py /path/to/repo --format json
```

自检（不扫任何文件，确认两个子扫描器本身工作正常）：

```bash
python release_gate.py --self-test
```

退出码：任一不过就返回 `1`，全过返回 `0`。直接接 CI：

```yaml
- run: python release_gate.py . --fail-on high
```

## 接入 CI

`.github/workflows/release-gate.yml` 已启用：每次 push/PR 先跑自检，再对代码目录
跑密钥闸、对 `samples/clean/` 跑合规闸，任一不过就让构建失败。上方状态徽章是真实状态。

`release_gate.py` 按同级目录查找两个子扫描器，所以 CI 会先把 `toksentry`、
`fin-compliance` 拉到父目录，复现本地的并列目录结构；也可以用
`--toksentry` / `--fin-compliance` 显式指定路径。内容闸只扫干净样本集，
不扫 README——文档里讲解规则时引用的违规例句不该算命中。

## 忽略清单

两个子扫描器各自认自己的忽略文件：

- `toksentry` 读 `<目录>/.toksentryignore`
- `fin-compliance` 读 `<目录>/.fincomplianceignore`

写入测试 fixture、示例代码、第三方目录即可，gitignore 语法。

## 许可

与 toksentry / fin-compliance 一致，MIT。
