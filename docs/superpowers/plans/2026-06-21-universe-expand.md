# 銘柄ユニバース拡張 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 日経225プリセット（コード+日本語名）を同梱し、config の `universe_preset` で監視銘柄を切替できるようにする。

**Architecture:** `screener/universe.py` が `presets/<name>.csv` を読み、`apply_preset(cfg)` で cfg["universe"]/cfg["names"] に反映。main/web の config 読込時に呼ぶだけで、取得・スクリーニングは無改修。

**Tech Stack:** Python 標準ライブラリ、既存スタック、pytest。追加依存なし。

## Global Constraints

- 追加依存なし。Python実行は venv 経由: `.venv\Scripts\python`（PowerShell、プロジェクトルートから）。
- 既定は `universe_preset: null`（現状の inline 40 を使用）。`"nikkei225"` で切替。
- inline の `names` はプリセット名より優先。未知/廃止コードは取得時に自動除外（既存）。
- nikkei225.csv はベストエフォート（日付明記）。データ健全性は最低限テストで担保。
- テストはネット非依存（`PRESETS_DIR` を monkeypatch / 同梱CSVの形チェック）。

---

### Task 1: universe.py（プリセット読込・cfg適用）

**Files:**
- Create: `screener/universe.py`
- Create: `tests/test_universe.py`

**Interfaces:**
- Produces: `universe.PRESETS_DIR`(Path)、`universe.load_preset(name) -> tuple[list[str], dict]`、
  `universe.apply_preset(cfg) -> None`。

- [ ] **Step 1: 失敗するテストを書く**

Create `tests/test_universe.py`:
```python
from screener import universe


def _write(tmp_path, monkeypatch, text):
    monkeypatch.setattr(universe, "PRESETS_DIR", tmp_path)
    (tmp_path / "dummy.csv").write_text(text, encoding="utf-8")


def test_load_preset_parses_and_skips(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch,
           "# comment\n\n7203.T,トヨタ自動車\n6758.T, ソニーグループ \nINVALIDLINE\n")
    tickers, names = universe.load_preset("dummy")
    assert tickers == ["7203.T", "6758.T"]          # コメント/空/不正行はスキップ
    assert names["7203.T"] == "トヨタ自動車"
    assert names["6758.T"] == "ソニーグループ"        # 前後空白は除去


def test_apply_preset_overrides_universe_inline_names_win(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch, "7203.T,トヨタ\n6758.T,ソニー\n")
    cfg = {"universe_preset": "dummy", "universe": ["X.T"],
           "names": {"7203.T": "トヨタ自動車(独自)"}}
    universe.apply_preset(cfg)
    assert cfg["universe"] == ["7203.T", "6758.T"]
    assert cfg["names"]["7203.T"] == "トヨタ自動車(独自)"  # inline優先
    assert cfg["names"]["6758.T"] == "ソニー"             # presetから


def test_apply_preset_noop_when_unset():
    cfg = {"universe": ["A.T"], "names": {"A.T": "x"}}
    universe.apply_preset(cfg)
    assert cfg["universe"] == ["A.T"] and cfg["names"] == {"A.T": "x"}
```

- [ ] **Step 2: 失敗を確認**

Run: `.venv\Scripts\python -m pytest tests/test_universe.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'screener.universe'`）

- [ ] **Step 3: 実装**

Create `screener/universe.py`:
```python
"""銘柄プリセット（presets/<name>.csv）の読込と config への適用。"""
from __future__ import annotations

from pathlib import Path

PRESETS_DIR = Path(__file__).resolve().parent.parent / "presets"


def load_preset(name):
    """presets/<name>.csv を (tickers, names) で返す。各行 `コード,日本語名`。
    `#` 始まり・空行・カンマ無し行はスキップ。"""
    path = PRESETS_DIR / f"{name}.csv"
    tickers, names = [], {}
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "," not in s:
            continue
        code, nm = s.split(",", 1)
        code, nm = code.strip(), nm.strip()
        if not code:
            continue
        tickers.append(code)
        names[code] = nm
    return tickers, names


def apply_preset(cfg):
    """cfg["universe_preset"] が設定されていれば universe/names を差し替える。
    inline の names を優先。未設定なら何もしない。"""
    name = cfg.get("universe_preset")
    if not name:
        return
    tickers, names = load_preset(name)
    cfg["universe"] = tickers
    cfg["names"] = {**names, **cfg.get("names", {})}
```

- [ ] **Step 4: テスト成功を確認**

Run: `.venv\Scripts\python -m pytest tests/test_universe.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: コミット**

```bash
git add screener/universe.py tests/test_universe.py
git commit -m "feat(universe): プリセット読込とcfg適用を追加"
```

---

### Task 2: 日経225プリセット同梱・配線・健全性テスト

**Files:**
- Create: `presets/nikkei225.csv`
- Modify: `config.yaml`
- Modify: `main.py`
- Modify: `web/app.py`
- Modify: `tests/test_universe.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `universe.apply_preset`, `universe.load_preset`（Task 1）。

- [ ] **Step 1: presets/nikkei225.csv を作成**

`presets/nikkei225.csv` を作成する。1行目はコメント、以降は `コード.T,日本語名`。
日経225構成銘柄をベストエフォートで列挙する（作成日を明記）。形式例（先頭部）:
```
# Nikkei225 constituents (best-effort, as of 2026-06-21). コード,日本語名
7203.T,トヨタ自動車
6758.T,ソニーグループ
6861.T,キーエンス
9984.T,ソフトバンクグループ
8306.T,三菱UFJフィナンシャル・グループ
9432.T,日本電信電話
6098.T,リクルートホールディングス
...
```
（全構成銘柄を記載。200件以上・全行 `.T` 付き・日本語名非空であること。実行時に
データ健全性テスト（Step 4）で検証する。）

- [ ] **Step 2: データ健全性テストを追記**

`tests/test_universe.py` に追記:
```python
def test_nikkei225_preset_is_healthy():
    tickers, names = universe.load_preset("nikkei225")
    assert len(tickers) >= 200                        # ほぼ225件
    assert all(t.endswith(".T") for t in tickers)     # 全行 .T 付き
    assert all(names[t] for t in tickers)             # 名称が空でない
    assert len(set(tickers)) == len(tickers)          # 重複なし
```

- [ ] **Step 3: 失敗を確認**

Run: `.venv\Scripts\python -m pytest tests/test_universe.py -k "nikkei225" -v`
Expected: ファイル未作成なら FAIL（FileNotFoundError）／作成済なら PASS。
Step 1 を先に行うため、ここでは PASS を確認する（件数・形式・重複の健全性）。

- [ ] **Step 4: config.yaml に universe_preset を追加**

`config.yaml` の `market: JP` 行の直後に追記:
```yaml
# 監視銘柄プリセット（null=下記 universe を使用 / "nikkei225"=presets/nikkei225.csv）
universe_preset: null
```

- [ ] **Step 5: main.load_cfg で apply_preset を呼ぶ**

`main.py` の import 群に追記:
```python
from screener import universe
```
`main.py` の `load_cfg` を次に置換:
```python
def load_cfg(path: str) -> dict:
    cfg = yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))
    universe.apply_preset(cfg)
    return cfg
```

- [ ] **Step 6: web/app.py で apply_preset を呼ぶ**

`web/app.py` の import 群に追記:
```python
from screener import universe  # noqa: E402
```
`web/app.py` の `CFG = yaml.safe_load(...)` の直後に追記:
```python
universe.apply_preset(CFG)
```

- [ ] **Step 7: 全テストと実データ確認**

Run: `.venv\Scripts\python -m pytest tests/ -q`
Expected: PASS（全件）

Run: `.venv\Scripts\python main.py value --top 3 --no-save`
Expected: 既定（universe_preset: null）のため従来の40銘柄で動作（取得中… 40銘柄）。

確認（225切替が読めること。設定ファイルを汚さずに）:
Run: `.venv\Scripts\python -c "import yaml; from screener import universe; c=yaml.safe_load(open('config.yaml',encoding='utf-8')); c['universe_preset']='nikkei225'; universe.apply_preset(c); print(len(c['universe']), c['universe'][:3])"`
Expected: 200以上の件数と先頭コードが表示される。

- [ ] **Step 8: README にプリセット切替を追記**

`README.md` の「## 設定」箇条書きに追記:
```markdown
- `universe_preset`: `nikkei225` で日経225（`presets/nikkei225.csv`）に切替（既定 null＝下記universe）。
  ※225銘柄は取得が長く、公開(無料枠)では重いことがある
```

- [ ] **Step 9: コミット**

```bash
git add presets/nikkei225.csv config.yaml main.py web/app.py tests/test_universe.py README.md
git commit -m "feat(universe): 日経225プリセット同梱とconfig切替を配線"
```

---

## Self-Review

- **Spec coverage:** load_preset/apply_preset=Task1 / nikkei225.csv同梱=Task2 Step1 / config.universe_preset=Task2 Step4 / main・web配線=Task2 Step5,6 / 健全性テスト=Task2 Step2 / README=Task2 Step8 / 既定40維持=universe_preset:null。全項目カバー。スコープ外（自動更新・他プリセット）は未着手で正しい。
- **Placeholder scan:** コードステップは実コード記載。`nikkei225.csv` の本文のみ「全構成銘柄を列挙（ベストエフォート）」とした（225行の curated データは実行時に作成し、Step2の健全性テスト＝件数/形式/重複/名称非空で品質を担保）。これはデータ生成であり、ロジックのプレースホルダではない。
- **Type consistency:** `load_preset(name)->(list[str], dict)`、`apply_preset(cfg)->None`、`PRESETS_DIR`(Path) を Task1 定義・Task2 で消費。main.load_cfg / web は apply_preset(cfg) を呼ぶのみで既存の cfg["universe"]/cfg["names"] 利用箇所と整合（無改修）。
