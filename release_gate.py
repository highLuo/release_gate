#!/usr/bin/env python3
"""release-gate - 发布前双闸：密钥泄露扫描 + 金融内容合规标注，一次跑完。

把 toksentry（密钥/令牌泄露扫描）与 fin-compliance（金融内容合规标注）
组合成一条命令：在发布/提交/打包之前，对代码与内容做一次联合体检，
任一不过就返回非零退出码，直接卡住流水线。两个子扫描器都是纯标准库、
零依赖，可离线运行。

设计目标：
- 一条命令同时管住「代码别漏密钥」和「文案别踩合规红线」两件事；
- 无第三方依赖，复制即用，适合塞进 CI、pre-commit 或私有化交付；
- 退出码对 CI 友好：发现密钥泄露或达到阈值的合规问题即失败。

用法：
  python release_gate.py <repo目录> [--fail-on high|medium|low|none]
  python release_gate.py --code-dir <代码目录> --content-dir <内容目录>
  python release_gate.py --self-test
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# 默认在同级目录下查找两个子扫描器
_TOKSENTRY_DEFAULT = os.path.normpath(os.path.join(HERE, "..", "toksentry", "toksentry.py"))
_FINCOMPLIANCE_DEFAULT = os.path.normpath(os.path.join(HERE, "..", "fin-compliance", "fin_compliance.py"))


def _import_modules(toksentry_path, fin_path):
    """把两个子扫描器所在目录加进 sys.path 并导入，返回 (toksentry, fin) 模块。"""
    import importlib.util

    mods = {}
    for key, path in (("toksentry", toksentry_path), ("fin", fin_path)):
        if not os.path.exists(path):
            raise FileNotFoundError("找不到子扫描器: %s" % path)
        dirname = os.path.dirname(path)
        if dirname not in sys.path:
            sys.path.insert(0, dirname)
        spec = importlib.util.spec_from_file_location(key, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mods[key] = mod
    return mods["toksentry"], mods["fin"]


_SEV_ORDER = {"high": 3, "medium": 2, "low": 1, "none": 0}


def _run_secret_scan(mod, code_dir):
    """返回 (findings, ignore_loaded) —— 复用 toksentry 的扫描与忽略逻辑。"""
    ignore_file = os.path.join(code_dir, ".toksentryignore")
    ignore = mod._load_ignore(ignore_file)
    findings = mod.scan_directory(code_dir, mod.load_rules(None), ignore=ignore)
    return findings, bool(ignore)


def _run_compliance_scan(mod, content_dir):
    ignore_file = os.path.join(content_dir, ".fincomplianceignore")
    ignore = mod._load_ignore(ignore_file)
    findings = mod.scan_directory(content_dir, mod.load_rules(None), ignore=ignore)
    return findings, bool(ignore)


def _print_table(secret_findings, compl_findings):
    print("\n" + "=" * 70)
    print("① 密钥/令牌泄露扫描 (toksentry)")
    print("=" * 70)
    if secret_findings:
        mod_t = _load_toksentry_output()
        mod_t(secret_findings) if mod_t else _dump(secret_findings)
    else:
        print("未发现密钥泄露。")

    print("\n" + "=" * 70)
    print("② 金融内容合规标注扫描 (fin-compliance)")
    print("=" * 70)
    if compl_findings:
        _dump_compliance(compl_findings)
    else:
        print("未发现合规风险标注问题。")


def _dump(findings):
    for f in findings:
        print("  %s | %s | entropy=%.3f | %s" % (
            f["file"], f["rule"], f.get("entropy", 0.0), f["match"][:40]))


def _dump_compliance(findings):
    for f in findings:
        line = f.get("line") or 0
        print("  %s:%s | %s | %s | %s" % (
            f["file"], line, f["severity"], f["category"], f["snippet"][:50]))


def _load_toksentry_output():
    # 延迟导入，仅在需要表格输出时复用 toksentry 自带格式
    try:
        import importlib
        toksentry = importlib.import_module("toksentry")
        return toksentry.output_table
    except Exception:
        return None


def _verdict(secret_findings, compl_findings, fail_on):
    secret_fail = len(secret_findings) > 0
    worst = max([_SEV_ORDER.get(f["severity"], 0) for f in compl_findings], default=0)
    threshold = _SEV_ORDER.get(fail_on, 3)
    compl_fail = worst >= threshold
    return secret_fail, compl_fail


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="release-gate - 发布前双闸：密钥扫描 + 金融内容合规")
    parser.add_argument("path", nargs="?", help="要扫描的根目录（同时作为代码与内容目录）")
    parser.add_argument("--code-dir", default=None, help="仅扫描密钥的目录（默认等于 path）")
    parser.add_argument("--content-dir", default=None, help="仅扫描合规的目录（默认等于 path）")
    parser.add_argument("--toksentry", default=_TOKSENTRY_DEFAULT, help="toksentry.py 路径")
    parser.add_argument("--fin-compliance", default=_FINCOMPLIANCE_DEFAULT, help="fin_compliance.py 路径")
    parser.add_argument("--fail-on", choices=["high", "medium", "low", "none"], default="high",
                        help="合规问题达到该严重级别即判失败（默认 high；none=只报告）")
    parser.add_argument("--format", choices=["table", "json"], default="table", help="输出格式")
    parser.add_argument("--self-test", action="store_true", help="分别运行两个子扫描器的自检后退出")
    args = parser.parse_args(argv)

    try:
        toksentry, fin = _import_modules(args.toksentry, args.fin_compliance)
    except Exception as e:
        print("[错误] 无法加载子扫描器: %s" % e, file=sys.stderr)
        return 2

    if args.self_test:
        ok1 = bool(toksentry.run_self_test())
        ok2 = bool(fin.run_self_test())
        print("[release-gate self-test] %s" % ("PASS" if (ok1 and ok2) else "FAIL"))
        return 0 if (ok1 and ok2) else 1

    if not args.path and not (args.code_dir or args.content_dir):
        parser.error("必须提供 path，或至少提供 --code-dir / --content-dir 之一")

    code_dir = args.code_dir or args.path
    content_dir = args.content_dir or args.path

    if code_dir and not os.path.exists(code_dir):
        print("[错误] 代码目录不存在: %s" % code_dir, file=sys.stderr)
        return 2
    if content_dir and not os.path.exists(content_dir):
        print("[错误] 内容目录不存在: %s" % content_dir, file=sys.stderr)
        return 2

    print("release-gate 双闸扫描")
    print("  代码目录 : %s" % code_dir)
    print("  内容目录 : %s" % content_dir)
    print("  合规阈值 : %s" % args.fail_on)

    secret_findings, secret_ign = ([], False)
    if code_dir:
        secret_findings, secret_ign = _run_secret_scan(toksentry, code_dir)
    compl_findings, compl_ign = ([], False)
    if content_dir:
        compl_findings, compl_ign = _run_compliance_scan(fin, content_dir)

    if args.format == "json":
        out = {
            "secret_findings": secret_findings,
            "compliance_findings": compl_findings,
            "secret_count": len(secret_findings),
            "compliance_count": len(compl_findings),
        }
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        _print_table(secret_findings, compl_findings)

    secret_fail, compl_fail = _verdict(secret_findings, compl_findings, args.fail_on)
    print("\n" + "-" * 70)
    print("结论:")
    print("  密钥泄露 : %s (%d 处)" % ("FAIL" if secret_fail else "PASS", len(secret_findings)))
    print("  内容合规 : %s (%d 处，阈值 %s)" % (
        "FAIL" if compl_fail else "PASS", len(compl_findings), args.fail_on))
    if secret_ign:
        print("  (已应用 .toksentryignore)")
    if compl_ign:
        print("  (已应用 .fincomplianceignore)")
    overall = secret_fail or compl_fail
    print("  总判定   : %s" % ("BLOCK 发布" if overall else "PASS 可发布"))
    return 1 if overall else 0


if __name__ == "__main__":
    sys.exit(main())
