"""sync_editor_dist.py

把 `grunt release` 产物 + 配套静态资源同步到 `nurse.board.ui/public/hmEditor/`。

同步范围
========

默认 (`--mode full`) 同步三块：

1. **editorDist 范围**（grunt release 产物）
   - `<editorDist>/` 根目录文件  →  目标根目录（仅 3 个 .min.* 文件，不递归 demo/）
   - `<editorDist>/css/`           →  目标 `css/`
   - `<editorDist>/js/`            →  目标 `js/`
   - `<editorDist>/iframe/`        →  目标 `iframe/`

2. **静态资源目录**（源仓库目录 → 目标对应目录）
   - `core/`、`drawingboard/`、`fonts/`、`img/`、`lang/`、
     `plugins/`、`skins/`、`styles/`、`vendor/`、`wrapper/`
   - `hmEditor/extensions/`        →  目标 `extensions/`
     （仍然需要——这是源码，与 `editorDist` 里的预编译产物并存）

3. **根目录文件**（源 hm-editor 根目录 → 目标根目录）
   - `ckeditor.js`、`config.js`、`contents.css`、`contents_new.css`、
     `hmEditor.js`、`print.css`、`styles.js`

清理策略
========

- 源里有、目标里没有              →  复制过去
- 源里和目标里都有但内容不同        →  默认覆盖；可加 `--protect-larger-target`
                                  在目标比源大时跳过覆盖（提示目标可能被手工修改）
- 源里和目标里都有且内容相同        →  跳过
- 目标里有、源里没有              →  视作孤儿，**按白名单规则删除**

清理白名单（永远不删）：
- `trans.txt` —— 部署说明
- `*.bak`、`*.bak.*` —— 任何 `.bak` 命名的文件

源目录
======

editorDist 源（按优先级探测）：
  1. `<workspace>/dev/builder/release/ckeditor/editorDist/`  （grunt release 完整产物）
  2. `<workspace>/editorDist/`                              （项目根，仅含前 7 步产物）

静态资源源：`<workspace>/` 下的项目根目录

目标目录
========

默认：`E:\\HDYY.YDHL\\Code\\nurse.board.ui\\public\\hmEditor`

使用
====

    python sync_editor_dist.py                  # 实际执行（full 模式）
    python sync_editor_dist.py --dry-run        # 只打印计划，不落地
    python sync_editor_dist.py --diff           # 只显示差异
    python sync_editor_dist.py --mode editorDist  # 只同步 editorDist 范围
    python sync_editor_dist.py --mode static     # 只同步静态资源
    python sync_editor_dist.py --no-clean       # 不清理孤儿
    python sync_editor_dist.py --protect-larger-target  # 目标比源大时跳过覆盖

退出码
======

    0  成功
    1  路径不存在或参数错误
    2  复制过程出错
"""
from __future__ import annotations

import argparse
import filecmp
import fnmatch
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


# ---------------------------------------------------------------------------
# 控制台输出编码跟随当前代码页（中文 Windows 默认 GBK/936，
# 若控制台已切到 UTF-8/65001 则用 UTF-8，避免中文乱码）
# ---------------------------------------------------------------------------

def _console_encoding() -> str:
    try:
        import ctypes

        cp = ctypes.windll.kernel32.GetConsoleOutputCP()
        if cp and cp != 65001:
            return f"cp{cp}"
    except Exception:
        pass
    return "utf-8"


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding=_console_encoding(), errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding=_console_encoding(), errors="replace")


# ---------------------------------------------------------------------------
# 路径配置
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE = SCRIPT_DIR.parent

DEFAULT_TARGET = Path(r"E:\HDYY.YDHL\Code\nurse.board.ui\public\hmEditor")

# 备份文件特征模式（复制时跳过；目标目录里这些文件也保留不删）
BACKUP_GLOBS = ("*.bak", "*.bak.*", "*.bak.*.*")

# 目标目录里永久保留的文件（不属于 hm-editor 源）
PRESERVED_FILES = ("trans.txt",)

# editorDist 拥有、可被覆盖/删除的根目录文件后缀
EDITOR_DIST_ROOT_SUFFIXES = (".min.css", ".min.js")


# ---------------------------------------------------------------------------
# 同步区域注册表
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StaticSyncSpec:
    """一个静态资源同步区域：源子目录 → 目标子目录。"""
    name: str
    src_subdir: str  # 相对于 WORKSPACE 的源子目录
    tgt_subdir: str  # 相对于 target 的目标子目录


STATIC_ZONES: tuple[StaticSyncSpec, ...] = (
    StaticSyncSpec("core",         "core",                "core"),
    StaticSyncSpec("drawingboard", "drawingboard",        "drawingboard"),
    StaticSyncSpec("fonts",        "fonts",               "fonts"),
    StaticSyncSpec("img",          "img",                 "img"),
    StaticSyncSpec("lang",         "lang",                "lang"),
    StaticSyncSpec("plugins",      "plugins",             "plugins"),
    StaticSyncSpec("skins",        "skins",               "skins"),
    StaticSyncSpec("styles",       "styles",              "styles"),
    StaticSyncSpec("vendor",       "vendor",              "vendor"),
    StaticSyncSpec("wrapper",      "wrapper",             "wrapper"),
    StaticSyncSpec("extensions",   "hmEditor/extensions", "extensions"),
)

STATIC_ROOT_FILES: tuple[str, ...] = (
    "ckeditor.js",
    "config.js",
    "contents.css",
    "contents_new.css",
    "hmEditor.js",
    "print.css",
    "styles.js",
)


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class ZonePlan:
    """单个同步区域的差异计划。"""

    name: str
    src: Path
    tgt: Path
    added: list[Path] = field(default_factory=list)
    updated: list[Path] = field(default_factory=list)        # 内容不同，将被覆盖
    protected: list[Path] = field(default_factory=list)      # 内容不同，但被 --protect-larger-target 跳过
    unchanged: list[Path] = field(default_factory=list)
    orphans: list[Path] = field(default_factory=list)
    errors: list[tuple[Path, str]] = field(default_factory=list)
    missing_in_source: bool = False

    @property
    def has_changes(self) -> bool:
        return any([self.added, self.updated, self.protected, self.unchanged,
                    self.orphans, self.errors])


@dataclass
class Plan:
    """一次同步的完整计划。"""

    zones: list[ZonePlan]

    @property
    def added(self) -> list[Path]:
        return [p for z in self.zones for p in z.added]

    @property
    def updated(self) -> list[Path]:
        return [p for z in self.zones for p in z.updated]

    @property
    def protected(self) -> list[Path]:
        return [p for z in self.zones for p in z.protected]

    @property
    def unchanged(self) -> list[Path]:
        return [p for z in self.zones for p in z.unchanged]

    @property
    def orphans(self) -> list[Path]:
        return [p for z in self.zones for p in z.orphans]

    @property
    def errors(self) -> list[tuple[Path, str]]:
        return [(p, m) for z in self.zones for p, m in z.errors]


# ---------------------------------------------------------------------------
# 路径解析
# ---------------------------------------------------------------------------

def _matches(name: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(name, g) for g in patterns)


def _is_backup_name(name: str) -> bool:
    return _matches(name, BACKUP_GLOBS)


def _is_preserved_name(name: str) -> bool:
    return name in PRESERVED_FILES


def _is_editor_dist_root_file(name: str) -> bool:
    """editorDist 根目录产物：仅 .min.css / .min.js。"""
    return name.endswith(EDITOR_DIST_ROOT_SUFFIXES)


def _iter_files(root: Path) -> Iterable[Path]:
    """遍历 root 下所有文件，但跳过 .bak 备份。"""
    if not root.is_dir():
        return
    for p in root.rglob("*"):
        if p.is_file() and not _is_backup_name(p.name):
            yield p


def _iter_direct_files(root: Path, *, suffix_filter: tuple[str, ...] | None = None) -> Iterable[Path]:
    """遍历 root 的直接子文件（不递归）。"""
    if not root.is_dir():
        return
    for p in root.iterdir():
        if not p.is_file():
            continue
        if _is_backup_name(p.name):
            continue
        if suffix_filter is not None and not p.name.endswith(suffix_filter):
            continue
        yield p


def resolve_editor_dist_source(workspace: Path) -> Path:
    """editorDist 源目录：优先 release 完整产物，降级到项目根的 editorDist。"""
    candidates = (
        workspace / "dev" / "builder" / "release" / "ckeditor" / "editorDist",
        workspace / "editorDist",
    )
    for cand in candidates:
        if cand.is_dir():
            return cand
    raise FileNotFoundError(
        "未找到 editorDist 目录。请确认已运行 `grunt release`。\n"
        "  候选路径：\n    "
        + "\n    ".join(str(c) for c in candidates)
    )


def resolve_target(arg: str | None) -> Path:
    if arg:
        tgt = Path(arg).resolve()
    else:
        tgt = DEFAULT_TARGET.resolve()
    if not tgt.is_dir():
        raise FileNotFoundError(f"目标目录不存在：{tgt}")
    return tgt


# ---------------------------------------------------------------------------
# 文件比较
# ---------------------------------------------------------------------------

def _files_equal(a: Path, b: Path) -> bool:
    """比较两个文件是否实质相同（大小 + 内容）。"""
    if not a.is_file() or not b.is_file():
        return False
    if a.stat().st_size != b.stat().st_size:
        return False
    try:
        return filecmp.cmp(a, b, shallow=False)
    except OSError:
        return False


# ---------------------------------------------------------------------------
# 单 zone 差异分析
# ---------------------------------------------------------------------------

def _plan_editor_dist_root(editor_dist_src: Path, tgt: Path, *, clean_orphans: bool,
                           protect_larger_target: bool) -> ZonePlan:
    """editorDist 根目录：只比对直接子文件（demo/ 等子目录不递归）。

    仅处理 .min.css / .min.js 文件（editorDist 根目录的合法产物）。
    对目标目录同名/同位置文件做差异分析；非 editorDist 风格的根目录文件
    既不复制也不删除（保留 nurs.board.ui 自己维护的文件）。
    """
    zp = ZonePlan(name="(root)", src=editor_dist_src, tgt=tgt)

    if not editor_dist_src.is_dir():
        zp.missing_in_source = True
        return zp

    src_files = {p.name: p for p in _iter_direct_files(editor_dist_src, suffix_filter=EDITOR_DIST_ROOT_SUFFIXES)}
    tgt_files = {p.name: p for p in _iter_direct_files(tgt, suffix_filter=EDITOR_DIST_ROOT_SUFFIXES)} if tgt.is_dir() else {}

    for name, sp in src_files.items():
        tp = tgt / name
        if tp.is_file():
            if _files_equal(sp, tp):
                zp.unchanged.append(tp)
            else:
                if protect_larger_target and tp.stat().st_size > sp.stat().st_size:
                    zp.protected.append(tp)
                else:
                    zp.updated.append(tp)
        else:
            zp.added.append(tp)

    if clean_orphans:
        for name, tp in tgt_files.items():
            if name in src_files:
                continue
            if _is_preserved_name(name):
                continue
            zp.orphans.append(tp)

    return zp


def _plan_directory_zone(name: str, src: Path, tgt: Path, *, clean_orphans: bool,
                         protect_larger_target: bool) -> ZonePlan:
    """递归比较 src 和 tgt 两个目录的内容（按相对路径）。"""
    zp = ZonePlan(name=name, src=src, tgt=tgt)

    if not src.is_dir():
        zp.missing_in_source = True
        if clean_orphans and tgt.is_dir():
            for f in tgt.rglob("*"):
                if f.is_file() and not _is_backup_name(f.name) and not _is_preserved_name(f.name):
                    zp.orphans.append(f)
        return zp

    src_files = {p.relative_to(src).as_posix(): p for p in _iter_files(src)}
    tgt_files = (
        {p.relative_to(tgt).as_posix(): p for p in _iter_files(tgt)}
        if tgt.is_dir() else {}
    )

    for rel, sp in src_files.items():
        tp = tgt / rel
        if tp.is_file():
            if _files_equal(sp, tp):
                zp.unchanged.append(tp)
            else:
                if protect_larger_target and tp.stat().st_size > sp.stat().st_size:
                    zp.protected.append(tp)
                else:
                    zp.updated.append(tp)
        else:
            zp.added.append(tp)

    if clean_orphans:
        for rel, tp in tgt_files.items():
            if rel not in src_files:
                zp.orphans.append(tp)

    return zp


def _plan_root_files_zone(name: str, src: Path, tgt: Path, *, clean_orphans: bool,
                          names: tuple[str, ...], protect_larger_target: bool) -> ZonePlan:
    """处理源根目录的指定文件列表（不递归）。"""
    zp = ZonePlan(name=name, src=src, tgt=tgt)

    if not src.is_dir():
        zp.missing_in_source = True
        return zp

    for name_ in names:
        if _is_backup_name(name_):
            continue
        sp = src / name_
        tp = tgt / name_
        if sp.is_file():
            if tp.is_file():
                if _files_equal(sp, tp):
                    zp.unchanged.append(tp)
                else:
                    if protect_larger_target and tp.stat().st_size > sp.stat().st_size:
                        zp.protected.append(tp)
                    else:
                        zp.updated.append(tp)
            else:
                zp.added.append(tp)

    if clean_orphans and tgt.is_dir():
        for name_ in names:
            if _is_backup_name(name_) or _is_preserved_name(name_):
                continue
            tp = tgt / name_
            sp = src / name_
            if tp.is_file() and not sp.is_file():
                zp.orphans.append(tp)

    return zp


# ---------------------------------------------------------------------------
# 计划构建
# ---------------------------------------------------------------------------

def build_editor_dist_zones(editor_dist_src: Path, tgt: Path, *, clean_orphans: bool,
                            protect_larger_target: bool) -> list[ZonePlan]:
    """editorDist 范围的同步计划（根目录 + css/ + js/ + iframe/）。"""
    zones: list[ZonePlan] = [
        _plan_editor_dist_root(
            editor_dist_src, tgt,
            clean_orphans=clean_orphans,
            protect_larger_target=protect_larger_target,
        ),
    ]
    for sub in ("css", "js", "iframe"):
        zones.append(_plan_directory_zone(
            sub, editor_dist_src / sub, tgt / sub,
            clean_orphans=clean_orphans,
            protect_larger_target=protect_larger_target,
        ))
    return zones


def build_static_zones(workspace: Path, tgt: Path, *, clean_orphans: bool,
                       protect_larger_target: bool) -> list[ZonePlan]:
    """静态资源同步计划（根目录文件 + 11 个目录）。"""
    zones: list[ZonePlan] = [
        _plan_root_files_zone(
            "(root-static)", workspace, tgt,
            clean_orphans=clean_orphans,
            names=STATIC_ROOT_FILES,
            protect_larger_target=protect_larger_target,
        ),
    ]
    for spec in STATIC_ZONES:
        src = workspace / spec.src_subdir
        zones.append(_plan_directory_zone(
            spec.name, src, tgt / spec.tgt_subdir,
            clean_orphans=clean_orphans,
            protect_larger_target=protect_larger_target,
        ))
    return zones


def build_plan(
    *,
    mode: str,
    workspace: Path,
    editor_dist_src: Path | None,
    tgt: Path,
    clean_orphans: bool,
    protect_larger_target: bool,
) -> Plan:
    zones: list[ZonePlan] = []
    if mode in ("editorDist", "full"):
        if editor_dist_src is None:
            raise ValueError("editorDist 模式需要提供 editor_dist_src")
        zones.extend(build_editor_dist_zones(
            editor_dist_src, tgt,
            clean_orphans=clean_orphans,
            protect_larger_target=protect_larger_target,
        ))
    if mode in ("static", "full"):
        zones.extend(build_static_zones(
            workspace, tgt,
            clean_orphans=clean_orphans,
            protect_larger_target=protect_larger_target,
        ))
    if mode not in ("editorDist", "static", "full"):
        raise ValueError(f"未知的 mode: {mode}")
    return Plan(zones=zones)


# ---------------------------------------------------------------------------
# 执行
# ---------------------------------------------------------------------------

def _apply_zone(zp: ZonePlan, *, dry_run: bool) -> None:
    """把一个 ZonePlan 落盘。"""
    if zp.missing_in_source:
        for tp in zp.orphans:
            if dry_run:
                continue
            try:
                tp.unlink()
            except OSError as exc:
                zp.errors.append((tp, str(exc)))
        return

    if zp.added or zp.updated:
        if not dry_run:
            zp.tgt.mkdir(parents=True, exist_ok=True)

    # 复制：新增 + 更新（protected 不复制）
    for tp in zp.added + zp.updated:
        if dry_run:
            continue
        try:
            rel = tp.relative_to(zp.tgt).as_posix()
            sp = zp.src / rel
            tp.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(sp, tp)
        except OSError as exc:
            zp.errors.append((tp, str(exc)))

    # 清理：孤儿
    for tp in zp.orphans:
        if dry_run:
            continue
        try:
            tp.unlink()
        except OSError as exc:
            zp.errors.append((tp, str(exc)))

    # 顺手清理空目录（仅执行模式）
    if not dry_run and zp.tgt.is_dir():
        for d in sorted(zp.tgt.rglob("*"), reverse=True):
            if d.is_dir() and not any(d.iterdir()):
                try:
                    d.rmdir()
                except OSError:
                    pass


def apply_plan(plan: Plan, *, dry_run: bool) -> None:
    for zp in plan.zones:
        _apply_zone(zp, dry_run=dry_run)


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------

def _rel(base: Path, p: Path) -> str:
    try:
        return p.relative_to(base).as_posix()
    except ValueError:
        return str(p)


def _print_zone(zp: ZonePlan, target: Path, *, max_items: int = 20) -> None:
    if not zp.has_changes:
        if zp.missing_in_source:
            print(f"  [{zp.name}]  源目录不存在，已标记为孤儿区域")
        return

    print(f"  [{zp.name}]")
    if zp.missing_in_source:
        print("    (源里没有此区域；目标里相关文件全部标记为孤儿)")

    for label, items in (
        ("新增", zp.added),
        ("更新", zp.updated),
        ("受保护（目标比源大，未覆盖）", zp.protected),
        ("无变化", zp.unchanged),
        ("孤儿（待清理）", zp.orphans),
    ):
        if not items:
            continue
        print(f"    {label}（{len(items)}）")
        for p in items[:max_items]:
            print(f"      - {_rel(target, p)}")
        if len(items) > max_items:
            print(f"      ... (其余 {len(items) - max_items} 项已省略)")

    if zp.errors:
        print(f"    错误（{len(zp.errors)}）")
        for p, msg in zp.errors:
            print(f"      - {_rel(target, p)}: {msg}")


def print_plan(plan: Plan, *, dry_run: bool, target: Path) -> None:
    mode = "[DRY-RUN] " if dry_run else ""
    print(f"{mode}同步目标：{target}")
    print("=" * 70)

    for zp in plan.zones:
        _print_zone(zp, target)

    print("=" * 70)
    n_add = sum(len(z.added) for z in plan.zones)
    n_upd = sum(len(z.updated) for z in plan.zones)
    n_prot = sum(len(z.protected) for z in plan.zones)
    n_eq = sum(len(z.unchanged) for z in plan.zones)
    n_orph = sum(len(z.orphans) for z in plan.zones)
    n_err = sum(len(z.errors) for z in plan.zones)
    print(
        f"汇总：+{n_add} 新增 / ~{n_upd} 更新 / !{n_prot} 受保护 "
        f"/ ={n_eq} 无变化 / -{n_orph} 待清理 / ✗{n_err} 错误"
    )


def print_diff(plan: Plan, target: Path) -> None:
    print(f"目标：{target}")
    print("=" * 70)
    for zp in plan.zones:
        if not (zp.added or zp.updated or zp.protected or zp.orphans):
            continue
        print(f"  [{zp.name}]")
        for label, items in (
            ("+ 新增", zp.added),
            ("~ 更新", zp.updated),
            ("! 受保护", zp.protected),
            ("- 孤儿", zp.orphans),
        ):
            if not items:
                continue
            print(f"    {label}（{len(items)}）")
            for p in items[:20]:
                print(f"      - {_rel(target, p)}")
            if len(items) > 20:
                print(f"      ... (其余 {len(items) - 20} 项已省略)")
    n_eq = sum(len(z.unchanged) for z in plan.zones)
    print(f"  = 无变化：{n_eq} 个（已省略）")
    print("=" * 70)


# ---------------------------------------------------------------------------
# 参数解析
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="把 grunt release 产物 + 静态资源同步到 nurse.board.ui/public/hmEditor",
    )
    parser.add_argument("--mode", choices=("editorDist", "static", "full"), default="full",
                        help="同步范围：editorDist 仅 grunt release 范围；static 仅静态资源；"
                             "full 两者都同步（默认）")
    parser.add_argument("--target", help="目标目录（默认 nurse.board.ui/public/hmEditor）")
    parser.add_argument("--dry-run", action="store_true", help="只打印计划，不落地")
    parser.add_argument("--no-clean", action="store_true", help="不清理孤儿文件")
    parser.add_argument("--diff", action="store_true", help="只显示差异")
    parser.add_argument("--protect-larger-target", action="store_true",
                        help="目标文件比源文件大时跳过覆盖（疑似手工修改）")
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    try:
        tgt = resolve_target(args.target)
    except FileNotFoundError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1

    editor_dist_src: Path | None = None
    if args.mode in ("editorDist", "full"):
        try:
            editor_dist_src = resolve_editor_dist_source(WORKSPACE)
        except FileNotFoundError as exc:
            print(f"错误：{exc}", file=sys.stderr)
            return 1
    else:
        editor_dist_src = WORKSPACE / "editorDist"

    clean = not args.no_clean
    protect = args.protect_larger_target

    plan = build_plan(
        mode=args.mode,
        workspace=WORKSPACE,
        editor_dist_src=editor_dist_src,
        tgt=tgt,
        clean_orphans=clean,
        protect_larger_target=protect,
    )

    if args.diff:
        print_diff(plan, tgt)
        return 0

    if args.dry_run:
        print_plan(plan, dry_run=True, target=tgt)
        return 0

    apply_plan(plan, dry_run=False)
    print_plan(plan, dry_run=False, target=tgt)

    if plan.errors:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
