# Coverage Visualizer - 完整實作規格文檔

**版本**: 1.0
**日期**: 2025-10-31
**目標**: 視覺化 LLM chunk 提取的覆蓋率，確保無資訊遺漏

---

## 📋 目錄

1. [專案概述](#1-專案概述)
2. [系統架構](#2-系統架構)
3. [Python 分析器規格](#3-python-分析器規格)
4. [JSON 輸出格式規格](#4-json-輸出格式規格)
5. [前端介面規格](#5-前端介面規格)
6. [顏色編碼系統](#6-顏色編碼系統)
7. [實作步驟指南](#7-實作步驟指南)
8. [技術決策說明](#8-技術決策說明)
9. [使用範例](#9-使用範例)
10. [擴展性考量](#10-擴展性考量)
11. [注意事項和限制](#11-注意事項和限制)

---

## 1. 專案概述

### 1.1 背景

在 LLM 驅動的文檔 chunking 系統中，我們需要驗證 chunk 提取過程是否完整覆蓋原始文檔，確保沒有資訊遺漏。現有系統將文檔分割成多個 chunks（存儲為 JSON），每個 chunk 包含 `original_text` 欄位（從原文提取的內容）。

### 1.2 核心目標

建立一個**完全獨立的視覺化工具**，可以：

1. **分析覆蓋率**：比對原始文檔和提取的 chunks，計算覆蓋百分比
2. **識別遺漏**：找出未被任何 chunk 覆蓋的內容（gaps）
3. **視覺化對應**：並排顯示原文和 chunks，高亮匹配關係
4. **互動探索**：點擊 chunk 即可在原文中看到對應位置

### 1.3 設計原則

- **完全獨立**：與現有 chunking 系統零耦合，放在獨立目錄 `tools/coverage_visualizer/`
- **前後端分離**：Python 負責分析生成 JSON，Vue.js 負責視覺化
- **無外部依賴**：Python 僅用標準庫，Vue.js 從 CDN 載入
- **易於使用**：雙擊 HTML 即可使用，無需複雜安裝

### 1.4 使用場景

- **開發階段**：驗證 chunking 演算法的完整性
- **調試階段**：找出為什麼某些內容未被提取
- **質量保證**：定期檢查不同文檔的覆蓋率
- **演示展示**：向他人展示 chunking 結果的視覺化對應

---

## 2. 系統架構

### 2.1 整體架構

```
┌─────────────────────────────────────────────────┐
│              使用者工作流程                      │
└─────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│  Step 1: Python 分析器 (analyzer.py)            │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│  輸入: 原始文檔 + chunks 目錄                   │
│  處理: 模糊匹配 + 覆蓋率分析                    │
│  輸出: coverage_report.json                     │
└─────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│  Step 2: Vue.js 前端 (viewer/)                  │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│  載入: coverage_report.json                     │
│  渲染: 雙欄並排 + 顏色編碼                      │
│  互動: 點擊、hover、滾動同步                    │
└─────────────────────────────────────────────────┘
```

### 2.2 資料流

```
原始文檔 (.md) ─┐
                ├──> analyzer.py ──> coverage_report.json ──> viewer/index.html ──> 用戶瀏覽器
chunks/ (.json)─┘
```

### 2.3 檔案結構

```
tools/coverage_visualizer/
├── analyzer.py                    # Python 分析腳本（獨立執行）
├── viewer/                        # 前端介面目錄
│   ├── index.html                # 主 HTML 頁面
│   ├── css/
│   │   └── style.css            # 所有樣式（佈局 + 顏色編碼）
│   ├── js/
│   │   └── app.js               # Vue.js 應用邏輯
│   └── data/
│       └── .gitkeep             # 存放生成的 JSON 文件
├── IMPLEMENTATION_SPEC.md         # 本文檔
└── README.md                      # 快速入門指南
```

### 2.4 技術棧

| 層級 | 技術 | 理由 |
|------|------|------|
| 後端分析 | Python 3.11+ 標準庫 | 與專案一致，無需額外依賴 |
| 模糊匹配 | difflib.SequenceMatcher | 標準庫，足夠準確 |
| 數據交換 | JSON | 通用格式，易於調試 |
| 前端框架 | Vue 3 (CDN) | 輕量、現代、無需 build |
| 樣式 | 純 CSS (Grid/Flexbox) | 無需預處理器 |
| Web Server | Python http.server | 標準庫，無需額外安裝 |

---

## 3. Python 分析器規格

### 3.1 功能概述

`analyzer.py` 是一個**獨立的 Python 腳本**，負責：

1. 讀取原始 Markdown 文檔
2. 讀取 chunks 目錄中的所有 JSON 文件
3. 使用模糊匹配找出每個 chunk 在原文中的位置
4. 分析覆蓋率並識別 gaps
5. 生成結構化的 JSON 報告

### 3.2 命令行介面

#### 基本用法

```bash
python analyzer.py \
  --document <原始文檔路徑> \
  --chunks <chunks目錄路徑> \
  --output <輸出JSON路徑> \
  [--threshold <相似度閾值>]
```

#### 參數說明

| 參數 | 必填 | 預設值 | 說明 |
|------|------|--------|------|
| `--document` | ✅ | - | 原始 Markdown 文檔的完整路徑 |
| `--chunks` | ✅ | - | 包含 chunk JSON 文件的目錄路徑 |
| `--output` | ✅ | - | 輸出 JSON 文件的路徑 |
| `--threshold` | ❌ | 0.90 | 模糊匹配的相似度閾值 (0.0-1.0) |

#### 範例

```bash
python tools/coverage_visualizer/analyzer.py \
  --document data/test/chapter_04_Depression_and_Suicidality.md \
  --chunks data/chunking_data_table_gemini_pro/chunks_claude_haiku/ \
  --output tools/coverage_visualizer/viewer/data/chapter_04_coverage.json \
  --threshold 0.90
```

### 3.3 模糊匹配演算法規格

#### 3.3.1 核心邏輯

使用 Python 標準庫的 `difflib.SequenceMatcher` 進行序列匹配。

**匹配流程**：

```
對於每個 chunk:
  1. 提取 chunk JSON 中的 "original_text" 欄位
  2. 在原始文檔中搜尋最佳匹配位置
  3. 使用滑動窗口掃描整個文檔
  4. 計算每個窗口位置的相似度分數
  5. 選擇相似度最高的位置作為匹配結果
  6. 如果最高相似度 >= threshold，標記為成功匹配
  7. 記錄匹配的起始位置、結束位置、相似度分數
```

#### 3.3.2 實作細節

**初始化 SequenceMatcher**：

```python
# 使用 difflib.SequenceMatcher
from difflib import SequenceMatcher

matcher = SequenceMatcher(None, chunk_text, document_text)
ratio = matcher.ratio()  # 返回 0.0-1.0 的相似度分數
```

**滑動窗口搜尋**：

- **窗口大小**：與 chunk 文本長度相同
- **步進**：每次移動 100 個字元（可調整以平衡性能和精度）
- **邊界處理**：窗口不超出文檔範圍

**相似度計算**：

- **SequenceMatcher.ratio()** 返回 0.0 到 1.0 之間的分數
- 計算公式：`2 * M / T`，其中 M 是匹配字元數，T 是總字元數
- **閾值判斷**：`ratio >= threshold` 則認為匹配成功

**優化策略**（可選）：

- 如果 chunk 很短（< 50 字元），使用更小的步進
- 如果 chunk 很長（> 2000 字元），使用更大的步進
- 考慮使用 `quick_ratio()` 或 `real_quick_ratio()` 進行預篩選

#### 3.3.3 匹配結果

每個 chunk 的匹配結果應包含：

```python
{
    "chunk_id": "章節ID",
    "match_start": 123,      # 在原文中的起始字元位置
    "match_end": 456,        # 在原文中的結束字元位置
    "similarity": 0.98,      # 相似度分數 (0.0-1.0)
    "matched": True          # 是否成功匹配（>= threshold）
}
```

### 3.4 Gap 識別和過濾規則

#### 3.4.1 Gap 定義

**Gap** = 原始文檔中未被任何 chunk 覆蓋的連續字元區域

#### 3.4.2 Gap 識別演算法

```
1. 初始化一個與文檔長度相同的布林陣列 covered[]，初始值為 False
2. 對於每個成功匹配的 chunk:
     將 covered[match_start:match_end] 設為 True
3. 掃描 covered[] 陣列，找出所有連續的 False 區段
4. 每個 False 區段即為一個 gap
```

#### 3.4.3 小 Gap 過濾規則

**定義**：小 gap = 長度 ≤ 5 個字元的 gap

**處理方式**：

- **在 `coverage_map` 中**：仍然標記為 `"type": "gap"`
- **在 `gaps` 列表中**：**不包含**小 gaps

**理由**：

- 小 gaps 通常是空白行、換行符、標點符號
- 這些不影響內容完整性
- 避免報告中充滿大量無意義的小 gaps

**實作邏輯**：

```python
# 識別所有 gaps
all_gaps = find_all_gaps(covered_array, document_text)

# 過濾掉小 gaps（僅用於 gaps 列表）
significant_gaps = [gap for gap in all_gaps if gap['length'] > 5]

# 但在 coverage_map 中仍保留所有 gaps
```

#### 3.4.4 Gap 資訊

每個 gap 應包含：

```python
{
    "gap_id": 1,                    # 順序編號
    "start": 12450,                 # 起始位置
    "end": 12680,                   # 結束位置
    "length": 230,                  # 長度（字元數）
    "content": "遺漏的內容文本..."   # 實際內容
}
```

### 3.5 Coverage Map 生成

**Coverage Map** 是一個有序陣列，記錄文檔每個區段的覆蓋狀態。

#### 3.5.1 目的

- 提供細粒度的覆蓋資訊
- 支援前端精確渲染顏色編碼
- 可用於計算統計數據

#### 3.5.2 結構

```python
[
    {
        "start": 0,
        "end": 2345,
        "type": "covered",
        "chunk_id": "chapter_04_chunk_001",
        "similarity": 0.98
    },
    {
        "start": 2345,
        "end": 2350,
        "type": "gap",
        "length": 5
    },
    {
        "start": 2350,
        "end": 5678,
        "type": "covered",
        "chunk_id": "chapter_04_chunk_002",
        "similarity": 0.95
    }
]
```

#### 3.5.3 生成演算法

```
1. 建立事件列表，包含所有 chunk 的 start 和 end
2. 排序事件列表
3. 從位置 0 開始掃描到文檔結尾
4. 對於每個區段：
     如果被 chunk 覆蓋 → type = "covered"
     否則 → type = "gap"
5. 合併相鄰的同類型區段（可選優化）
```

### 3.6 錯誤處理

#### 3.6.1 輸入驗證

- **文檔文件不存在**：打印錯誤訊息並退出
- **chunks 目錄不存在**：打印錯誤訊息並退出
- **chunks 目錄為空**：打印警告，生成空報告
- **輸出路徑的目錄不存在**：自動創建目錄

#### 3.6.2 解析錯誤

- **JSON 解析失敗**：記錄錯誤的文件名，跳過該文件，繼續處理其他文件
- **缺少 `original_text` 欄位**：跳過該 chunk，記錄警告

#### 3.6.3 匹配失敗

- **相似度 < threshold**：標記為未匹配，但仍記錄在報告中（`matched: false`）
- **完全無法匹配**：相似度 = 0.0，標記為未匹配

#### 3.6.4 輸出格式

所有錯誤和警告應同時：
1. 打印到 console（使用 `print()` 或 `logging`）
2. 記錄在 JSON 的 `metadata.warnings` 欄位中

---

## 4. JSON 輸出格式規格

### 4.1 完整 Schema

```json
{
  "metadata": {
    "document_name": "string",        // 原始文檔檔名
    "document_path": "string",        // 原始文檔完整路徑
    "document_length": "integer",     // 文檔字元數
    "chunks_directory": "string",     // chunks 目錄路徑
    "total_chunks": "integer",        // 總 chunk 數量
    "matched_chunks": "integer",      // 成功匹配的 chunk 數量
    "unmatched_chunks": "integer",    // 未匹配的 chunk 數量
    "coverage_percentage": "float",   // 覆蓋率百分比 (0-100)
    "total_gaps": "integer",          // 總 gap 數量（包含小 gaps）
    "significant_gaps": "integer",    // 顯著 gap 數量（長度 > 5）
    "threshold": "float",             // 使用的相似度閾值
    "generated_at": "string",         // ISO 8601 時間戳
    "warnings": ["string"]            // 警告訊息列表（如果有）
  },
  "original_text": "string",          // 完整的原始文檔內容
  "chunks": [
    {
      "chunk_id": "string",           // chunk 的唯一 ID
      "file_name": "string",          // chunk 的原始檔名
      "match_start": "integer",       // 匹配起始位置
      "match_end": "integer",         // 匹配結束位置
      "similarity": "float",          // 相似度分數 (0.0-1.0)
      "matched": "boolean",           // 是否成功匹配
      "extracted_text": "string",     // chunk 的 original_text 內容
      "contextual_prefix": "string",  // chunk 的前言（如果有）
      "metadata": {                   // chunk 的 metadata（來自原始 JSON）
        "chapter_title": "string",
        "section_title": "string",
        "subsection_title": ["string"],
        "summary": "string"
      }
    }
  ],
  "gaps": [
    {
      "gap_id": "integer",            // gap 順序編號
      "start": "integer",             // 起始位置
      "end": "integer",               // 結束位置
      "length": "integer",            // 長度（字元數）
      "content": "string"             // 遺漏的內容文本
    }
  ],
  "coverage_map": [
    {
      "start": "integer",
      "end": "integer",
      "type": "covered" | "gap",
      "chunk_id": "string",           // 如果 type = "covered"
      "similarity": "float",          // 如果 type = "covered"
      "length": "integer"             // 如果 type = "gap"
    }
  ]
}
```

### 4.2 欄位說明

#### 4.2.1 metadata 欄位

| 欄位 | 類型 | 說明 |
|------|------|------|
| `document_name` | string | 文檔檔名（不含路徑），例："chapter_04_Depression_and_Suicidality.md" |
| `document_path` | string | 文檔完整路徑，用於追蹤來源 |
| `document_length` | integer | 文檔總字元數，用於計算覆蓋率 |
| `chunks_directory` | string | chunks 目錄路徑 |
| `total_chunks` | integer | 找到的 chunk JSON 文件總數 |
| `matched_chunks` | integer | 相似度 >= threshold 的 chunk 數量 |
| `unmatched_chunks` | integer | 相似度 < threshold 的 chunk 數量 |
| `coverage_percentage` | float | 覆蓋率：(覆蓋的字元數 / 總字元數) * 100 |
| `total_gaps` | integer | 所有 gap 的數量（包含小 gaps） |
| `significant_gaps` | integer | 長度 > 5 的 gap 數量 |
| `threshold` | float | 使用的相似度閾值 |
| `generated_at` | string | 生成時間，ISO 8601 格式，例："2025-10-31T12:34:56.789Z" |
| `warnings` | array | 處理過程中的警告訊息，例：["chunk_042.json: 缺少 original_text 欄位"] |

#### 4.2.2 chunks 陣列

**排序**：按照 `match_start` 升序排列（即原文出現順序）

**每個 chunk 物件**：

| 欄位 | 類型 | 說明 |
|------|------|------|
| `chunk_id` | string | chunk 的唯一識別符，來自 JSON 的 "chunk_id" 欄位 |
| `file_name` | string | chunk JSON 的檔名，方便追溯 |
| `match_start` | integer | 在原文中的起始字元位置（0-based） |
| `match_end` | integer | 在原文中的結束字元位置（不含） |
| `similarity` | float | 相似度分數，範圍 0.0-1.0 |
| `matched` | boolean | 是否成功匹配（similarity >= threshold） |
| `extracted_text` | string | chunk JSON 中的 "original_text" 內容 |
| `contextual_prefix` | string | chunk JSON 中的 "contextual_prefix" 欄位（如果存在） |
| `metadata` | object | chunk 的完整 metadata 物件（原封不動複製） |

#### 4.2.3 gaps 陣列

**排序**：按照 `start` 升序排列

**過濾**：僅包含長度 > 5 的 gaps

**每個 gap 物件**：

| 欄位 | 類型 | 說明 |
|------|------|------|
| `gap_id` | integer | gap 的順序編號（從 1 開始） |
| `start` | integer | 在原文中的起始位置 |
| `end` | integer | 在原文中的結束位置（不含） |
| `length` | integer | gap 的長度（字元數）= end - start |
| `content` | string | gap 的實際內容文本 |

#### 4.2.4 coverage_map 陣列

**排序**：按照 `start` 升序排列

**連續性**：相鄰區段應無縫連接（前一個的 end = 下一個的 start）

**每個區段物件**：

| 欄位 | 類型 | 必填條件 | 說明 |
|------|------|----------|------|
| `start` | integer | 總是 | 區段起始位置 |
| `end` | integer | 總是 | 區段結束位置 |
| `type` | string | 總是 | "covered" 或 "gap" |
| `chunk_id` | string | type = "covered" | 對應的 chunk ID |
| `similarity` | float | type = "covered" | 相似度分數 |
| `length` | integer | type = "gap" | gap 長度 |

### 4.3 數據範例

簡化範例（僅展示結構）：

```json
{
  "metadata": {
    "document_name": "chapter_04_Depression_and_Suicidality.md",
    "document_path": "/path/to/data/test/chapter_04_Depression_and_Suicidality.md",
    "document_length": 119603,
    "chunks_directory": "/path/to/chunks/",
    "total_chunks": 51,
    "matched_chunks": 50,
    "unmatched_chunks": 1,
    "coverage_percentage": 98.47,
    "total_gaps": 25,
    "significant_gaps": 8,
    "threshold": 0.90,
    "generated_at": "2025-10-31T12:34:56.789Z",
    "warnings": []
  },
  "original_text": "Depression is one of the most common...",
  "chunks": [
    {
      "chunk_id": "chapter_04_chunk_001",
      "file_name": "chapter_04_Depression_and_Suicidality_chunk_001.json",
      "match_start": 0,
      "match_end": 2345,
      "similarity": 0.98,
      "matched": true,
      "extracted_text": "Depression is one of...",
      "contextual_prefix": "This chunk introduces...",
      "metadata": {
        "chapter_title": "Depression and Suicidality",
        "section_title": "Introduction",
        "subsection_title": [],
        "summary": "Overview of depression..."
      }
    }
  ],
  "gaps": [
    {
      "gap_id": 1,
      "start": 12450,
      "end": 12680,
      "length": 230,
      "content": "\n\n## Missing Section\n\nThis content was not extracted..."
    }
  ],
  "coverage_map": [
    {
      "start": 0,
      "end": 2345,
      "type": "covered",
      "chunk_id": "chapter_04_chunk_001",
      "similarity": 0.98
    },
    {
      "start": 2345,
      "end": 2350,
      "type": "gap",
      "length": 5
    }
  ]
}
```

---

## 5. 前端介面規格

### 5.1 整體佈局

#### 5.1.1 頁面結構

```
┌─────────────────────────────────────────────────────────┐
│  Header (固定在頂部)                                     │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│  🎯 Coverage Visualizer                                  │
│  📁 [File Picker] 或 自動掃描 data/ 目錄                │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│  📊 統計面板                                             │
│     覆蓋率: 98.5% | Chunks: 51 | 顯著 Gaps: 8           │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│  🎚️ 閾值調整: [━━━●━━━] 90%                            │
└─────────────────────────────────────────────────────────┘
┌──────────────────────┬──────────────────────────────────┐
│  📄 原始文檔 (左欄)   │  📦 Chunks 列表 (右欄)           │
│  ━━━━━━━━━━━━━━━━━  │  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                      │                                  │
│  [可滾動內容區域]    │  [可滾動內容區域]                │
│  - 顏色編碼的文本    │  - Chunk 卡片列表                │
│  - 點擊高亮          │  - 按原文位置排序                │
│                      │                                  │
└──────────────────────┴──────────────────────────────────┘
```

#### 5.1.2 響應式設計

- **桌面** (≥ 1024px)：左右並排，各佔 50% 寬度
- **平板** (768px - 1023px)：左右並排，左 40% 右 60%
- **手機** (< 768px)：上下堆疊，原文在上，chunks 在下

### 5.2 HTML 結構規劃

#### 5.2.1 主要元素

```html
<div id="app">
  <header class="header">
    <!-- 標題、檔案選擇器、統計面板、閾值滑桿 -->
  </header>

  <main class="main-container">
    <div class="left-panel">
      <!-- 原始文檔顯示區 -->
    </div>

    <div class="right-panel">
      <!-- Chunks 列表 -->
    </div>
  </main>
</div>
```

#### 5.2.2 關鍵組件

**1. Header 區域**

```html
<header class="header">
  <h1>📊 Coverage Visualizer</h1>

  <div class="file-loader">
    <input type="file" accept=".json" @change="loadJSON">
    <span>或自動掃描 data/ 目錄</span>
  </div>

  <div class="stats-panel">
    <span class="stat">覆蓋率: {{ coveragePercentage }}%</span>
    <span class="stat">Chunks: {{ totalChunks }}</span>
    <span class="stat">顯著 Gaps: {{ significantGaps }}</span>
  </div>

  <div class="threshold-control">
    <label>相似度閾值:</label>
    <input type="range" min="80" max="100" v-model="threshold">
    <span>{{ threshold }}%</span>
  </div>
</header>
```

**2. 左欄 - 原始文檔**

```html
<div class="left-panel" @scroll="onLeftScroll">
  <h2>📄 原始文檔</h2>

  <div class="document-content">
    <!-- 使用 v-for 渲染 coverage_map 中的每個區段 -->
    <span
      v-for="segment in coverageMap"
      :key="segment.start"
      :class="getSegmentClass(segment)"
      @click="onSegmentClick(segment)"
    >
      {{ getSegmentText(segment) }}
    </span>
  </div>
</div>
```

**3. 右欄 - Chunks 列表**

```html
<div class="right-panel" @scroll="onRightScroll">
  <h2>📦 Chunks ({{ chunks.length }})</h2>

  <div class="chunks-list">
    <div
      v-for="chunk in chunks"
      :key="chunk.chunk_id"
      :class="['chunk-card', { 'active': activeChunkId === chunk.chunk_id }]"
      @click="onChunkClick(chunk)"
      @mouseenter="onChunkHover(chunk)"
      @mouseleave="onChunkLeave"
    >
      <div class="chunk-header">
        <span class="chunk-id">{{ chunk.chunk_id }}</span>
        <span class="similarity-badge" :class="getSimilarityClass(chunk.similarity)">
          {{ (chunk.similarity * 100).toFixed(1) }}%
        </span>
      </div>

      <div class="chunk-meta">
        <span>📍 位置: {{ chunk.match_start }} - {{ chunk.match_end }}</span>
        <span>📄 {{ chunk.metadata.section_title }}</span>
      </div>

      <div class="chunk-preview" v-if="expandedChunkId === chunk.chunk_id">
        <p><strong>提取的文本:</strong></p>
        <pre>{{ chunk.extracted_text }}</pre>
      </div>
    </div>
  </div>
</div>
```

### 5.3 CSS 樣式規格

#### 5.3.1 佈局

**主容器**：

```css
.main-container {
  display: grid;
  grid-template-columns: 1fr 1fr;  /* 左右各 50% */
  gap: 20px;
  height: calc(100vh - 200px);  /* 減去 header 高度 */
}

.left-panel, .right-panel {
  overflow-y: auto;
  padding: 20px;
  border: 1px solid #ddd;
  border-radius: 8px;
}
```

**響應式調整**：

```css
@media (max-width: 1023px) {
  .main-container {
    grid-template-columns: 40% 60%;
  }
}

@media (max-width: 767px) {
  .main-container {
    grid-template-columns: 1fr;  /* 單欄 */
  }
}
```

#### 5.3.2 顏色編碼樣式

**相似度分級**（根據第 6 節的規格）：

```css
/* 高相似度：綠色 */
.segment-high {
  background-color: #d4edda;  /* 淺綠 */
  border-bottom: 2px solid #28a745;
}

/* 中相似度：黃色 */
.segment-medium {
  background-color: #fff3cd;  /* 淺黃 */
  border-bottom: 2px solid #ffc107;
}

/* 低相似度：橘色 */
.segment-low {
  background-color: #ffe5d0;  /* 淺橘 */
  border-bottom: 2px solid #fd7e14;
}

/* Gap：白色/灰底 */
.segment-gap {
  background-color: #f8f9fa;  /* 淺灰 */
  color: #6c757d;
}

/* 小 gap：更淺的灰色 */
.segment-small-gap {
  background-color: #ffffff;
  color: #adb5bd;
}
```

**互動狀態**：

```css
/* 點擊高亮 */
.segment-active {
  background-color: #007bff !important;
  color: white !important;
  font-weight: bold;
}

/* Hover 效果 */
.segment-high:hover,
.segment-medium:hover,
.segment-low:hover {
  opacity: 0.8;
  cursor: pointer;
}
```

#### 5.3.3 Chunk 卡片樣式

```css
.chunk-card {
  border: 1px solid #dee2e6;
  border-radius: 8px;
  padding: 15px;
  margin-bottom: 15px;
  background: white;
  transition: all 0.3s ease;
}

.chunk-card:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  transform: translateY(-2px);
}

.chunk-card.active {
  border-color: #007bff;
  box-shadow: 0 0 0 3px rgba(0,123,255,0.25);
}

.similarity-badge {
  display: inline-block;
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 0.85em;
  font-weight: bold;
}

.similarity-high { background-color: #28a745; color: white; }
.similarity-medium { background-color: #ffc107; color: black; }
.similarity-low { background-color: #fd7e14; color: white; }
```

### 5.4 Vue.js 組件架構

#### 5.4.1 主應用結構

```javascript
const app = Vue.createApp({
  data() {
    return {
      // 數據狀態
      jsonData: null,           // 載入的 JSON 數據
      threshold: 90,            // 當前閾值 (%)
      activeChunkId: null,      // 當前激活的 chunk ID
      expandedChunkId: null,    // 當前展開的 chunk ID
      hoveredChunkId: null,     // 當前 hover 的 chunk ID

      // 滾動同步狀態
      isLeftScrolling: false,
      isRightScrolling: false
    }
  },

  computed: {
    // 計算屬性
    coveragePercentage() { /* ... */ },
    chunks() { /* ... */ },
    coverageMap() { /* ... */ },
    significantGaps() { /* ... */ }
  },

  methods: {
    // 方法（詳見 5.5 節）
    loadJSON() { /* ... */ },
    onChunkClick() { /* ... */ },
    onSegmentClick() { /* ... */ },
    onLeftScroll() { /* ... */ },
    onRightScroll() { /* ... */ }
  }
})

app.mount('#app')
```

#### 5.4.2 數據狀態管理

**核心狀態**：

| 狀態 | 類型 | 說明 |
|------|------|------|
| `jsonData` | Object | 載入的完整 JSON 數據 |
| `threshold` | Number | 當前相似度閾值（80-100） |
| `activeChunkId` | String | 被點擊激活的 chunk ID |
| `expandedChunkId` | String | 被展開顯示詳情的 chunk ID |
| `hoveredChunkId` | String | 當前 hover 的 chunk ID |
| `isLeftScrolling` | Boolean | 防止滾動同步循環的標誌 |
| `isRightScrolling` | Boolean | 防止滾動同步循環的標誌 |

**計算屬性**：

| 計算屬性 | 返回類型 | 說明 |
|---------|---------|------|
| `coveragePercentage` | Number | 覆蓋率百分比 |
| `chunks` | Array | 過濾後的 chunks 列表 |
| `coverageMap` | Array | 根據當前閾值重新計算的 coverage map |
| `totalChunks` | Number | chunk 總數 |
| `significantGaps` | Number | 顯著 gap 數量 |

### 5.5 互動功能詳細規格

#### 5.5.1 JSON 載入

**方式 1：文件選擇器**

```javascript
methods: {
  loadJSON(event) {
    const file = event.target.files[0]
    const reader = new FileReader()

    reader.onload = (e) => {
      try {
        this.jsonData = JSON.parse(e.target.result)
        this.showNotification('JSON 載入成功')
      } catch (error) {
        this.showError('JSON 解析失敗: ' + error.message)
      }
    }

    reader.readAsText(file)
  }
}
```

**方式 2：自動掃描 data/ 目錄**

```javascript
mounted() {
  // 嘗試載入預設的 JSON 文件
  this.scanDataDirectory()
}

methods: {
  async scanDataDirectory() {
    // 使用 fetch 嘗試載入 data/ 目錄中的 JSON
    const files = ['chapter_04_coverage.json', /* ... */]

    for (const file of files) {
      try {
        const response = await fetch(`data/${file}`)
        if (response.ok) {
          this.jsonData = await response.json()
          break
        }
      } catch (e) {
        // 繼續嘗試下一個文件
      }
    }
  }
}
```

#### 5.5.2 點擊 Chunk 互動

**行為**：

1. 在右欄 chunks 列表中點擊某個 chunk 卡片
2. 該 chunk 卡片被標記為 active（藍色邊框）
3. 左欄原文滾動到該 chunk 對應的位置
4. 該 chunk 在原文中的文本被高亮顯示（藍色背景）

**實作**：

```javascript
methods: {
  onChunkClick(chunk) {
    // 設置激活狀態
    this.activeChunkId = chunk.chunk_id

    // 滾動到左欄對應位置
    this.scrollToPosition('left-panel', chunk.match_start)

    // 高亮原文中的對應區段
    this.highlightSegment(chunk.match_start, chunk.match_end)
  },

  scrollToPosition(panelClass, charPosition) {
    // 計算字元位置對應的滾動位置
    // 這需要知道文本渲染後的實際像素位置
    const panel = document.querySelector(`.${panelClass}`)
    const targetElement = this.findElementAtPosition(charPosition)

    if (targetElement) {
      targetElement.scrollIntoView({
        behavior: 'smooth',
        block: 'center'
      })
    }
  }
}
```

#### 5.5.3 Hover Chunk 顯示詳情

**行為**：

1. 鼠標懸停在 chunk 卡片上
2. 顯示額外資訊：
   - 完整的 metadata
   - 相似度分數
   - 文件名

**實作**：

```javascript
methods: {
  onChunkHover(chunk) {
    this.hoveredChunkId = chunk.chunk_id
    // 可選：在左欄輕微高亮對應位置（不滾動）
  },

  onChunkLeave() {
    this.hoveredChunkId = null
  }
}
```

**CSS**：

```css
.chunk-card .hover-tooltip {
  display: none;
}

.chunk-card:hover .hover-tooltip {
  display: block;
  position: absolute;
  background: rgba(0,0,0,0.8);
  color: white;
  padding: 10px;
  border-radius: 4px;
  z-index: 10;
}
```

#### 5.5.4 滾動同步

**行為**：

- 當用戶滾動左欄原文時，右欄 chunks 列表自動高亮當前可見的 chunks
- 當用戶滾動右欄 chunks 時，左欄原文自動滾動到對應位置

**實作重點**：

1. **防止循環觸發**：使用 `isLeftScrolling` 和 `isRightScrolling` 標誌
2. **計算可見範圍**：使用 `IntersectionObserver` 或手動計算
3. **平滑滾動**：使用 `scrollIntoView({ behavior: 'smooth' })`

```javascript
methods: {
  onLeftScroll(event) {
    if (this.isRightScrolling) return

    this.isLeftScrolling = true

    // 計算當前可見的字元範圍
    const visibleRange = this.getVisibleCharRange('left-panel')

    // 找出在該範圍內的 chunks
    const visibleChunks = this.chunks.filter(chunk =>
      chunk.match_start <= visibleRange.end &&
      chunk.match_end >= visibleRange.start
    )

    // 高亮右欄對應的 chunks
    if (visibleChunks.length > 0) {
      this.activeChunkId = visibleChunks[0].chunk_id
    }

    setTimeout(() => { this.isLeftScrolling = false }, 100)
  },

  onRightScroll(event) {
    // 類似邏輯，但方向相反
  }
}
```

#### 5.5.5 閾值調整

**行為**：

1. 拖動滑桿改變閾值（80%-100%）
2. 即時重新計算顏色編碼
3. 更新統計數據（覆蓋率、匹配 chunks 數量）

**實作**：

```javascript
computed: {
  // 根據當前閾值重新計算 coverage map
  coverageMap() {
    if (!this.jsonData) return []

    // 根據 threshold 重新分類每個區段
    return this.jsonData.coverage_map.map(segment => {
      if (segment.type === 'covered') {
        const thresholdValue = this.threshold / 100

        // 重新判斷相似度等級
        if (segment.similarity >= 0.95) {
          return { ...segment, class: 'high' }
        } else if (segment.similarity >= thresholdValue) {
          return { ...segment, class: 'medium' }
        } else {
          return { ...segment, class: 'low' }
        }
      }
      return segment
    })
  }
}
```

**Watch**：

```javascript
watch: {
  threshold(newVal, oldVal) {
    // 保存到 localStorage
    localStorage.setItem('coverageThreshold', newVal)

    // 可選：顯示提示
    this.showNotification(`閾值已調整為 ${newVal}%`)
  }
}
```

### 5.6 localStorage 使用

**保存用戶偏好**：

```javascript
mounted() {
  // 載入保存的設置
  const savedThreshold = localStorage.getItem('coverageThreshold')
  if (savedThreshold) {
    this.threshold = parseInt(savedThreshold)
  }
}

methods: {
  savePreference(key, value) {
    localStorage.setItem(key, JSON.stringify(value))
  },

  loadPreference(key, defaultValue) {
    const saved = localStorage.getItem(key)
    return saved ? JSON.parse(saved) : defaultValue
  }
}
```

---

## 6. 顏色編碼系統

### 6.1 相似度分級標準

| 等級 | 相似度範圍 | 顏色 | 含義 |
|------|-----------|------|------|
| **高** (High) | ≥ 95% | 🟢 綠色 | 幾乎完美匹配，可信度極高 |
| **中** (Medium) | 90% - 94.9% | 🟡 黃色 | 良好匹配，可能有些微差異（標點、空白） |
| **低** (Low) | threshold - 89.9% | 🟠 橘色 | 可疑匹配，需要人工確認 |
| **Gap** | N/A | ⚪ 灰色 | 未匹配的內容 |
| **小 Gap** | 長度 ≤ 5 | 淡灰 | 可忽略的空白或標點 |

### 6.2 顏色對應表

#### 6.2.1 背景色

| 分級 | 背景色 (Hex) | RGB | 用途 |
|------|-------------|-----|------|
| High | `#d4edda` | rgb(212, 237, 218) | 高相似度區段背景 |
| Medium | `#fff3cd` | rgb(255, 243, 205) | 中相似度區段背景 |
| Low | `#ffe5d0` | rgb(255, 229, 208) | 低相似度區段背景 |
| Gap | `#f8f9fa` | rgb(248, 249, 250) | Gap 區段背景 |
| Small Gap | `#ffffff` | rgb(255, 255, 255) | 小 gap 背景（白色） |

#### 6.2.2 邊框色

| 分級 | 邊框色 (Hex) | 用途 |
|------|-------------|------|
| High | `#28a745` | 綠色底線 |
| Medium | `#ffc107` | 黃色底線 |
| Low | `#fd7e14` | 橘色底線 |
| Gap | `#dee2e6` | 灰色邊框 |

#### 6.2.3 Badge 顏色（Chunk 卡片中的相似度徽章）

| 分級 | 背景色 | 文字色 |
|------|--------|--------|
| High | `#28a745` | `#ffffff` |
| Medium | `#ffc107` | `#000000` |
| Low | `#fd7e14` | `#ffffff` |

### 6.3 CSS 類別命名規範

#### 6.3.1 原文區段

```css
.segment-high       /* 高相似度區段 */
.segment-medium     /* 中相似度區段 */
.segment-low        /* 低相似度區段 */
.segment-gap        /* Gap 區段 */
.segment-small-gap  /* 小 Gap 區段 */
.segment-active     /* 當前激活的區段（點擊後） */
```

#### 6.3.2 Chunk 卡片

```css
.chunk-card              /* 基礎 chunk 卡片 */
.chunk-card.active       /* 激活狀態的 chunk 卡片 */
.similarity-badge        /* 相似度徽章 */
.similarity-high         /* 高相似度徽章 */
.similarity-medium       /* 中相似度徽章 */
.similarity-low          /* 低相似度徽章 */
```

### 6.4 動態顏色更新邏輯

**當用戶調整閾值時**：

```javascript
methods: {
  getSegmentClass(segment) {
    if (segment.type === 'gap') {
      return segment.length <= 5 ? 'segment-small-gap' : 'segment-gap'
    }

    // 根據當前閾值動態判斷
    const threshold = this.threshold / 100
    const similarity = segment.similarity

    if (similarity >= 0.95) {
      return 'segment-high'
    } else if (similarity >= 0.90) {
      return 'segment-medium'
    } else if (similarity >= threshold) {
      return 'segment-low'
    } else {
      // 相似度低於閾值，視為未匹配
      return 'segment-gap'
    }
  },

  getSimilarityClass(similarity) {
    if (similarity >= 0.95) return 'similarity-high'
    if (similarity >= 0.90) return 'similarity-medium'
    return 'similarity-low'
  }
}
```

---

## 7. 實作步驟指南

### Phase 1: Python 分析器開發

#### Step 1: 建立專案結構

```bash
mkdir -p tools/coverage_visualizer
cd tools/coverage_visualizer
touch analyzer.py
mkdir -p viewer/{css,js,data}
touch viewer/index.html viewer/css/style.css viewer/js/app.js
```

#### Step 2: 實作命令行參數解析

在 `analyzer.py` 中：

1. 導入必要模組：`argparse`, `json`, `pathlib`, `difflib`, `datetime`
2. 建立 `ArgumentParser`
3. 定義四個參數：`--document`, `--chunks`, `--output`, `--threshold`
4. 添加參數驗證邏輯

**重點**：

- 使用 `pathlib.Path` 處理路徑
- 檢查文件/目錄是否存在
- 提供有意義的錯誤訊息

#### Step 3: 實作模糊匹配核心邏輯

**子任務**：

1. **讀取原始文檔**
   - 使用 `Path.read_text(encoding='utf-8')` 讀取
   - 處理可能的編碼錯誤

2. **讀取 chunks 目錄**
   - 使用 `Path.glob('*.json')` 找出所有 JSON
   - 解析每個 JSON，提取 `chunk_id` 和 `original_text`
   - 處理 JSON 解析錯誤和缺少欄位的情況

3. **實作模糊匹配函數**

   ```python
   def find_best_match(chunk_text, document_text, threshold):
       """
       找出 chunk_text 在 document_text 中的最佳匹配位置

       返回: {
           'match_start': int,
           'match_end': int,
           'similarity': float,
           'matched': bool
       }
       """
   ```

   **演算法**：
   - 使用滑動窗口掃描文檔
   - 對每個窗口位置使用 `SequenceMatcher.ratio()` 計算相似度
   - 記錄最高相似度的位置
   - 如果最高相似度 >= threshold，標記為成功匹配

4. **優化性能**
   - 對於長文檔，使用較大的步進（如 100 字元）
   - 可選：使用 `quick_ratio()` 進行預篩選

#### Step 4: 實作覆蓋率分析

**子任務**：

1. **建立覆蓋陣列**
   - 建立長度為 `len(document_text)` 的布林陣列
   - 初始值全為 `False`

2. **標記已覆蓋區域**
   - 對每個成功匹配的 chunk，設置 `covered[start:end] = True`

3. **識別 gaps**
   - 掃描 `covered` 陣列，找出所有連續的 `False` 區段
   - 記錄每個 gap 的起始、結束位置和內容

4. **過濾小 gaps**
   - 分離出長度 > 5 的 gaps 作為 `significant_gaps`
   - 保留所有 gaps 用於生成 `coverage_map`

5. **生成 coverage_map**
   - 按順序遍歷文檔
   - 對每個連續區段，標記為 "covered" 或 "gap"
   - 記錄相關資訊（chunk_id, similarity）

#### Step 5: 實作 JSON 輸出

**子任務**：

1. **建立 metadata 物件**
   - 計算覆蓋率：`(覆蓋的字元數 / 總字元數) * 100`
   - 統計 matched/unmatched chunks
   - 記錄處理過程中的警告

2. **組裝 chunks 陣列**
   - 按 `match_start` 排序
   - 包含所有必要欄位（參考第 4 節）

3. **組裝 gaps 陣列**
   - 僅包含長度 > 5 的 gaps
   - 按 `start` 排序

4. **組裝 coverage_map 陣列**
   - 確保連續性（相鄰區段無縫連接）
   - 包含所有 gaps（包括小 gaps）

5. **寫入 JSON 文件**
   - 使用 `json.dump(data, f, indent=2, ensure_ascii=False)`
   - 確保輸出目錄存在（使用 `Path.mkdir(parents=True, exist_ok=True)`）

6. **打印摘要**
   - 顯示覆蓋率、chunks 數量、gaps 數量等關鍵統計

---

### Phase 2: 前端介面開發

#### Step 1: HTML 框架

在 `viewer/index.html` 中：

1. **基本結構**
   ```html
   <!DOCTYPE html>
   <html lang="zh-TW">
   <head>
     <meta charset="UTF-8">
     <meta name="viewport" content="width=device-width, initial-scale=1.0">
     <title>Coverage Visualizer</title>
     <link rel="stylesheet" href="css/style.css">
   </head>
   <body>
     <div id="app">
       <!-- Vue 應用掛載點 -->
     </div>

     <!-- 從 CDN 載入 Vue 3 -->
     <script src="https://unpkg.com/vue@3/dist/vue.global.js"></script>
     <script src="js/app.js"></script>
   </body>
   </html>
   ```

2. **添加 HTML 模板**（參考 5.2 節）
   - Header 區域
   - 左右欄結構
   - 使用 Vue 指令：`v-for`, `v-if`, `@click`, `:class`

#### Step 2: CSS 樣式實作

在 `viewer/css/style.css` 中：

1. **Reset 和基礎樣式**
   ```css
   * { box-sizing: border-box; margin: 0; padding: 0; }
   body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
   ```

2. **佈局樣式**（參考 5.3.1）
   - Grid 佈局
   - 響應式媒體查詢

3. **顏色編碼樣式**（參考 5.3.2）
   - `.segment-high`, `.segment-medium`, `.segment-low`, `.segment-gap`
   - Hover 和 active 狀態

4. **Chunk 卡片樣式**（參考 5.3.3）
   - 卡片佈局、陰影、圓角
   - 相似度徽章

5. **動畫和過渡**
   ```css
   .chunk-card { transition: all 0.3s ease; }
   .segment-active { transition: background-color 0.2s; }
   ```

#### Step 3: Vue.js 應用初始化

在 `viewer/js/app.js` 中：

1. **建立 Vue 應用**
   ```javascript
   const { createApp } = Vue

   const app = createApp({
     data() {
       return {
         jsonData: null,
         threshold: 90,
         activeChunkId: null,
         // ... 其他狀態
       }
     }
   })

   app.mount('#app')
   ```

2. **添加基本計算屬性**
   - `coveragePercentage`
   - `chunks`
   - `totalChunks`

#### Step 4: 實作 JSON 載入

1. **文件選擇器**（參考 5.5.1）
   - 使用 `FileReader` API
   - 錯誤處理和用戶提示

2. **自動掃描 data/ 目錄**
   - 使用 `fetch` API
   - 嘗試載入預設文件

#### Step 5: 實作核心互動功能

**按優先級順序實作**：

1. **點擊 Chunk 高亮原文**（參考 5.5.2）
   - `onChunkClick` 方法
   - `scrollToPosition` 方法
   - 使用 `scrollIntoView` API

2. **Hover 顯示詳情**（參考 5.5.3）
   - `onChunkHover` 和 `onChunkLeave` 方法
   - CSS tooltip 或 Vue 條件渲染

3. **閾值調整**（參考 5.5.5）
   - 使用 `watch` 監聽閾值變化
   - 重新計算 `coverageMap`
   - 保存到 localStorage

4. **滾動同步**（參考 5.5.4）
   - `onLeftScroll` 和 `onRightScroll` 方法
   - 防止循環觸發
   - 使用 `debounce` 優化性能

#### Step 6: 完善用戶體驗

1. **載入狀態**
   - 添加 loading spinner
   - 顯示載入進度

2. **錯誤處理**
   - 友善的錯誤訊息
   - 提供重試機制

3. **通知系統**
   - 成功/失敗的 toast 通知
   - 使用簡單的 CSS 動畫

4. **鍵盤快捷鍵**（可選）
   - 方向鍵切換 chunks
   - Escape 鍵取消高亮

---

### Phase 3: 整合測試與優化

#### Step 1: 功能驗證

1. **測試 Python 分析器**
   ```bash
   python analyzer.py \
     --document data/test/chapter_04_Depression_and_Suicidality.md \
     --chunks data/chunking_data_table_gemini_pro/chunks_claude_haiku/ \
     --output viewer/data/test_output.json
   ```

   **檢查點**：
   - JSON 是否成功生成
   - 覆蓋率計算是否合理（應該 > 95%）
   - Gaps 數量是否正常
   - 所有 chunks 是否都被處理

2. **測試前端介面**
   ```bash
   cd viewer
   python -m http.server 8000
   ```

   **檢查點**：
   - JSON 是否正確載入
   - 左右欄是否正確渲染
   - 顏色編碼是否正確
   - 點擊互動是否正常
   - 滾動同步是否流暢

#### Step 2: 邊界情況測試

1. **測試極端情況**
   - 非常短的文檔（< 100 字元）
   - 非常長的文檔（> 100KB）
   - 沒有 chunks 的情況
   - 所有 chunks 都未匹配的情況
   - 100% 覆蓋率的理想情況

2. **測試錯誤處理**
   - 不存在的文檔路徑
   - 損壞的 JSON 文件
   - 缺少必要欄位的 JSON
   - 編碼錯誤的文檔

#### Step 3: 性能優化

1. **Python 分析器優化**
   - 使用更大的滑動窗口步進
   - 對於長 chunks，使用 `quick_ratio()` 預篩選
   - 考慮使用多線程處理多個 chunks

2. **前端性能優化**
   - 使用 `v-memo` 或 `v-once` 減少不必要的重新渲染
   - 對於大文檔，使用虛擬滾動（可選）
   - 使用 `debounce` 優化滾動事件處理

#### Step 4: 文檔和範例

1. **更新 README.md**
   - 快速入門指南
   - 常見問題 FAQ
   - 截圖示例

2. **準備示例數據**
   - 至少一個完整的示例 JSON
   - 放在 `viewer/data/` 目錄中

---

## 8. 技術決策說明

### 8.1 為什麼選擇 difflib？

**理由**：

1. **標準庫**：無需額外安裝，減少依賴
2. **成熟穩定**：Python 標準庫的一部分，經過廣泛測試
3. **足夠準確**：對於本專案的需求，difflib 的精度已經足夠
4. **簡單易用**：API 簡潔，易於理解和維護

**替代方案對比**：

| 工具 | 優點 | 缺點 | 為什麼不選 |
|------|------|------|-----------|
| **difflib** | 標準庫、簡單 | 性能一般 | ✅ 選擇 |
| rapidfuzz | 性能極佳 | 需要額外安裝 | 本專案優先考慮零依賴 |
| fuzzywuzzy | 功能豐富 | 需要額外安裝 | 功能過於複雜 |
| Levenshtein | 精確的編輯距離 | 需要編譯 | 安裝複雜度高 |

**性能考量**：

- 對於中等大小的文檔（< 200KB），difflib 的性能完全可接受
- 如果未來需要處理超大文檔，可以考慮切換到 rapidfuzz

### 8.2 為什麼使用 Vue 3 CDN？

**理由**：

1. **零構建工具**：不需要 npm、webpack、vite 等
2. **快速開發**：直接在 HTML 中使用，立即看到結果
3. **易於分發**：整個 `viewer/` 目錄可以直接分享
4. **現代化**：Vue 3 提供 Composition API 和更好的性能
5. **輕量級**：從 CDN 載入，不增加專案體積

**替代方案對比**：

| 框架 | 優點 | 缺點 | 為什麼不選 |
|------|------|------|-----------|
| **Vue 3 CDN** | 簡單、現代 | 無類型檢查 | ✅ 選擇 |
| React CDN | 生態豐富 | JSX 語法複雜 | 不適合無構建工具的場景 |
| Vanilla JS | 零依賴 | 代碼冗長 | 開發效率低 |
| Alpine.js | 輕量級 | 功能有限 | 不支援複雜狀態管理 |

### 8.3 小 gap 閾值設定為 5 的理由

**理由**：

1. **過濾噪音**：空白行、單個換行符、標點符號通常 ≤ 5 字元
2. **專注重要遺漏**：只關注可能影響內容完整性的 gaps
3. **減少報告混亂**：避免報告中充滿大量無意義的小 gaps

**實驗數據**（根據經驗估計）：

| 閾值 | 過濾掉的 gaps | 保留的顯著 gaps | 用戶體驗 |
|------|--------------|----------------|---------|
| 1 字元 | 5% | 95% | 報告過於冗長 |
| 5 字元 | 60-70% | 30-40% | ✅ 平衡 |
| 10 字元 | 80% | 20% | 可能遺漏重要 gaps |

**可調整性**：

- 未來可以考慮讓用戶在前端介面調整這個閾值
- 類似於相似度閾值的滑桿

### 8.4 預設相似度 90% 的考量

**理由**：

1. **平衡嚴格與寬容**：
   - 95% 太嚴格：可能將正常的格式差異標記為未匹配
   - 85% 太寬鬆：可能將錯誤匹配標記為成功

2. **允許合理差異**：
   - 空白字元的差異（空格、tab、換行）
   - 標點符號的微小變化
   - Unicode 字元的不同編碼

3. **可調整性**：
   - 前端提供滑桿讓用戶自行調整
   - 不同文檔可能需要不同的閾值

**實驗建議**：

建議用戶先用 90% 處理，然後根據結果調整：

- 如果看到很多黃色區段（90-95%），可以降低到 85%
- 如果看到很多橘色區段（低於 90%），可以提高到 95%

---

## 9. 使用範例

### 9.1 基本使用流程

#### Step 1: 生成分析數據

```bash
cd /path/to/langgraph

python tools/coverage_visualizer/analyzer.py \
  --document data/test/chapter_04_Depression_and_Suicidality.md \
  --chunks data/chunking_data_table_gemini_pro/chunks_claude_haiku/ \
  --output tools/coverage_visualizer/viewer/data/chapter_04_coverage.json
```

**預期輸出**：

```
正在讀取文檔: chapter_04_Depression_and_Suicidality.md
文檔長度: 119603 字元

正在掃描 chunks 目錄...
找到 51 個 chunk 文件

正在進行模糊匹配...
[1/51] 處理 chapter_04_chunk_001... 相似度: 98.5%
[2/51] 處理 chapter_04_chunk_002... 相似度: 96.2%
...
[51/51] 處理 chapter_04_chunk_051... 相似度: 97.8%

正在分析覆蓋率...
總字元數: 119603
已覆蓋: 117820 字元 (98.51%)
未覆蓋: 1783 字元 (1.49%)

識別出 25 個 gaps（包含小 gaps）
其中 8 個為顯著 gaps（長度 > 5）

成功生成 JSON 報告: tools/coverage_visualizer/viewer/data/chapter_04_coverage.json
```

#### Step 2: 啟動 Web Server

```bash
cd tools/coverage_visualizer/viewer
python -m http.server 8000
```

**預期輸出**：

```
Serving HTTP on :: port 8000 (http://[::]:8000/) ...
```

#### Step 3: 打開瀏覽器

在瀏覽器中訪問：`http://localhost:8000`

### 9.2 進階使用

#### 調整相似度閾值

```bash
python tools/coverage_visualizer/analyzer.py \
  --document data/test/chapter_04_Depression_and_Suicidality.md \
  --chunks data/chunking_data_table_gemini_pro/chunks_claude_haiku/ \
  --output tools/coverage_visualizer/viewer/data/chapter_04_strict.json \
  --threshold 0.95
```

**效果**：更嚴格的匹配標準，更多 chunks 可能被標記為未匹配

#### 批次處理多個文檔

```bash
# 使用簡單的 bash 腳本
for doc in data/test/*.md; do
  filename=$(basename "$doc" .md)
  python tools/coverage_visualizer/analyzer.py \
    --document "$doc" \
    --chunks "data/chunking_data_table_gemini_pro/chunks_claude_haiku/" \
    --output "tools/coverage_visualizer/viewer/data/${filename}_coverage.json"
done
```

### 9.3 前端使用技巧

#### 快速定位問題區域

1. 查看統計面板，如果覆蓋率 < 95%，可能有問題
2. 滾動到右欄，查找相似度 < 90% 的 chunks（橘色徽章）
3. 點擊這些 chunks，在左欄查看對應位置
4. 檢查是否為真正的問題或僅是格式差異

#### 調整閾值以探索不同情況

1. 將閾值降低到 85%，看看是否有更多 chunks 被匹配
2. 將閾值提高到 95%，看看是否有完美匹配的 chunks

#### 識別系統性問題

如果發現多個連續的 gaps，可能表示：

- Chunking 演算法遺漏了某個章節
- 某些格式的內容（如表格、列表）未被正確處理
- LLM 提取時出現了系統性錯誤

---

## 10. 擴展性考量

### 10.1 未來可能的功能增強

#### 10.1.1 多文檔比較

**功能**：在同一介面中比較多個文檔的覆蓋率

**實作思路**：

1. 修改 Python 分析器，支援批次處理
2. 修改 JSON 格式，添加多文檔支援
3. 前端添加文檔切換器或標籤頁

**JSON 格式擴展**：

```json
{
  "documents": [
    {
      "document_name": "chapter_04.md",
      "metadata": { /* ... */ },
      "chunks": [ /* ... */ ],
      "gaps": [ /* ... */ ]
    },
    {
      "document_name": "chapter_05.md",
      /* ... */
    }
  ],
  "summary": {
    "total_documents": 2,
    "average_coverage": 97.8,
    "total_gaps": 15
  }
}
```

#### 10.1.2 Gap 分類

**功能**：自動分類 gaps 的類型（格式問題 vs 內容遺漏）

**實作思路**：

1. 分析 gap 的內容特徵
2. 使用正則表達式識別常見模式
3. 分類為：空白行、表格、代碼塊、純文本等

**分類邏輯**：

```python
def classify_gap(content):
    if content.strip() == '':
        return 'whitespace'
    elif re.match(r'^\|.*\|$', content, re.MULTILINE):
        return 'table'
    elif re.match(r'^```', content):
        return 'code_block'
    elif len(content.split('\n')) == 1:
        return 'single_line'
    else:
        return 'paragraph'
```

#### 10.1.3 匯出報告

**功能**：將覆蓋率分析結果匯出為 PDF 或 HTML 報告

**實作思路**：

1. 使用 Python 的 `reportlab` 或 `weasyprint` 生成 PDF
2. 或者使用瀏覽器的列印功能生成 PDF
3. 包含統計數據、圖表、問題列表

#### 10.1.4 互動式編輯

**功能**：在介面中直接編輯 chunk 的匹配位置

**實作思路**：

1. 允許用戶手動調整 chunk 的起始/結束位置
2. 實時更新覆蓋率統計
3. 匯出修正後的 JSON

**使用場景**：

- 當自動匹配出錯時，手動糾正
- 微調匹配邊界以提高覆蓋率

#### 10.1.5 與 Chunking 系統集成

**功能**：直接從 chunking pipeline 調用 coverage visualizer

**實作思路**：

1. 將 `analyzer.py` 封裝為可導入的模組
2. 在 chunking 完成後自動生成覆蓋率報告
3. 如果覆蓋率 < 閾值，發出警告

### 10.2 性能優化方向

#### 10.2.1 大文檔處理

**問題**：當文檔 > 1MB 時，模糊匹配可能很慢

**解決方案**：

1. 使用 `quick_ratio()` 預篩選
2. 使用多線程並行處理 chunks
3. 考慮使用 rapidfuzz 替代 difflib

#### 10.2.2 前端虛擬滾動

**問題**：當 chunks 數量 > 100 時，DOM 節點過多

**解決方案**：

1. 使用虛擬滾動庫（如 vue-virtual-scroller）
2. 僅渲染可見區域的 chunks
3. 懶加載原文內容

### 10.3 可維護性增強

#### 10.3.1 配置文件

**功能**：使用配置文件替代命令行參數

**範例 `config.yaml`**：

```yaml
analyzer:
  threshold: 0.90
  min_gap_size: 5
  step_size: 100  # 滑動窗口步進

output:
  format: json
  pretty_print: true
  include_warnings: true

viewer:
  default_theme: light
  auto_load: true
  sync_scroll: true
```

#### 10.3.2 日誌系統

**功能**：使用 Python logging 模組記錄詳細日誌

**實作**：

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('coverage_analyzer.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
logger.info('開始處理文檔...')
```

---

## 11. 注意事項和限制

### 11.1 已知限制

#### 11.1.1 模糊匹配的局限性

**限制**：

1. **性能問題**：
   - 對於超大文檔（> 5MB），匹配可能需要數分鐘
   - 解決方案：使用更大的步進或切換到 rapidfuzz

2. **匹配錯誤**：
   - 如果原文中有高度重複的內容，可能匹配到錯誤的位置
   - 解決方案：人工檢查低相似度的匹配

3. **編碼問題**：
   - 如果原文和 chunk 使用不同的 Unicode 正規化，可能導致匹配失敗
   - 解決方案：統一使用 NFC 正規化

#### 11.1.2 瀏覽器性能限制

**限制**：

1. **大文檔渲染**：
   - 當原文 > 500KB 時，瀏覽器可能變慢
   - 解決方案：使用虛擬滾動或分頁顯示

2. **記憶體使用**：
   - 載入的 JSON 完全存儲在記憶體中
   - 解決方案：對於超大文檔，考慮後端分頁載入

#### 11.1.3 相似度計算的主觀性

**限制**：

- 90% 的閾值是經驗值，不同文檔可能需要不同的閾值
- 使用者需要根據實際情況調整

### 11.2 瀏覽器兼容性

**支援的瀏覽器**：

| 瀏覽器 | 最低版本 | 備註 |
|--------|---------|------|
| Chrome | 90+ | 推薦 |
| Firefox | 88+ | 推薦 |
| Safari | 14+ | 部分 CSS 可能需要調整 |
| Edge | 90+ | Chromium 版本 |

**不支援**：

- IE 11 及以下（Vue 3 不支援）
- 過舊版本的行動瀏覽器

### 11.3 安全考量

#### 11.3.1 本地文件存取

**問題**：

- 瀏覽器的同源政策可能阻止直接載入本地 JSON
- 使用 `file://` 協議時，fetch API 可能失敗

**解決方案**：

- 必須使用 HTTP server（如 `python -m http.server`）
- 或者使用文件選擇器讓用戶手動上傳 JSON

#### 11.3.2 敏感資料

**注意**：

- 如果原始文檔包含敏感資訊，生成的 JSON 也會包含
- 不要將包含敏感資訊的 JSON 上傳到公開的 Web server

### 11.4 常見問題

#### Q1: 為什麼某些 chunks 的相似度很低？

**可能原因**：

1. LLM 提取時修改了原文（如修正拼寫錯誤）
2. 原文包含特殊格式（如表格），LLM 轉換為純文本
3. 編碼問題導致某些字元不匹配

**解決方案**：

- 檢查該 chunk 的 `extracted_text` 和原文的對應位置
- 如果是格式轉換問題，屬於正常現象
- 如果是錯誤提取，需要修正 chunking 演算法

#### Q2: 為什麼覆蓋率無法達到 100%？

**可能原因**：

1. 文檔包含表格、圖片說明等特殊格式，未被提取
2. Chunking 演算法有意忽略某些內容（如頁碼、頁首頁尾）
3. 存在小 gaps（≤ 5 字元），如空白行

**判斷方法**：

- 查看 `gaps` 列表，檢查遺漏的內容
- 如果都是空白行或標點，則正常
- 如果包含實質內容，需要改進 chunking 演算法

#### Q3: 為什麼前端載入 JSON 失敗？

**可能原因**：

1. 未使用 HTTP server，而是直接用 `file://` 協議打開
2. JSON 文件路徑錯誤
3. JSON 格式錯誤（語法錯誤）

**解決方案**：

1. 確保使用 `python -m http.server` 啟動本地伺服器
2. 檢查瀏覽器的 Console 查看錯誤訊息
3. 使用 JSON validator 檢查 JSON 格式

#### Q4: 滾動同步不流暢怎麼辦？

**可能原因**：

1. 文檔太大，DOM 節點過多
2. 滾動事件處理沒有使用 debounce

**解決方案**：

1. 實作虛擬滾動
2. 使用 `lodash.debounce` 或自行實作 debounce
3. 減少 chunks 卡片的複雜度

---

## 12. 附錄

### 12.1 完整的命令行幫助

```bash
$ python analyzer.py --help

usage: analyzer.py [-h] --document DOCUMENT --chunks CHUNKS --output OUTPUT
                   [--threshold THRESHOLD]

Coverage Analyzer - 分析 LLM chunk 提取的覆蓋率

required arguments:
  --document DOCUMENT    原始文檔的路徑 (.md 文件)
  --chunks CHUNKS        包含 chunk JSON 文件的目錄路徑
  --output OUTPUT        輸出 JSON 文件的路徑

optional arguments:
  -h, --help            顯示此幫助訊息並退出
  --threshold THRESHOLD  模糊匹配的相似度閾值 (0.0-1.0)，預設 0.90

範例:
  python analyzer.py \
    --document data/test/chapter_04.md \
    --chunks data/chunks/ \
    --output viewer/data/report.json \
    --threshold 0.90
```

### 12.2 JSON Schema (完整定義)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Coverage Report",
  "type": "object",
  "required": ["metadata", "original_text", "chunks", "gaps", "coverage_map"],
  "properties": {
    "metadata": {
      "type": "object",
      "required": [
        "document_name", "document_length", "total_chunks",
        "matched_chunks", "coverage_percentage", "threshold", "generated_at"
      ],
      "properties": {
        "document_name": { "type": "string" },
        "document_path": { "type": "string" },
        "document_length": { "type": "integer", "minimum": 0 },
        "chunks_directory": { "type": "string" },
        "total_chunks": { "type": "integer", "minimum": 0 },
        "matched_chunks": { "type": "integer", "minimum": 0 },
        "unmatched_chunks": { "type": "integer", "minimum": 0 },
        "coverage_percentage": { "type": "number", "minimum": 0, "maximum": 100 },
        "total_gaps": { "type": "integer", "minimum": 0 },
        "significant_gaps": { "type": "integer", "minimum": 0 },
        "threshold": { "type": "number", "minimum": 0, "maximum": 1 },
        "generated_at": { "type": "string", "format": "date-time" },
        "warnings": { "type": "array", "items": { "type": "string" } }
      }
    },
    "original_text": { "type": "string" },
    "chunks": {
      "type": "array",
      "items": {
        "type": "object",
        "required": [
          "chunk_id", "file_name", "match_start", "match_end",
          "similarity", "matched", "extracted_text"
        ],
        "properties": {
          "chunk_id": { "type": "string" },
          "file_name": { "type": "string" },
          "match_start": { "type": "integer", "minimum": 0 },
          "match_end": { "type": "integer", "minimum": 0 },
          "similarity": { "type": "number", "minimum": 0, "maximum": 1 },
          "matched": { "type": "boolean" },
          "extracted_text": { "type": "string" },
          "contextual_prefix": { "type": "string" },
          "metadata": { "type": "object" }
        }
      }
    },
    "gaps": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["gap_id", "start", "end", "length", "content"],
        "properties": {
          "gap_id": { "type": "integer", "minimum": 1 },
          "start": { "type": "integer", "minimum": 0 },
          "end": { "type": "integer", "minimum": 0 },
          "length": { "type": "integer", "minimum": 1 },
          "content": { "type": "string" }
        }
      }
    },
    "coverage_map": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["start", "end", "type"],
        "properties": {
          "start": { "type": "integer", "minimum": 0 },
          "end": { "type": "integer", "minimum": 0 },
          "type": { "enum": ["covered", "gap"] },
          "chunk_id": { "type": "string" },
          "similarity": { "type": "number" },
          "length": { "type": "integer" }
        }
      }
    }
  }
}
```

### 12.3 推薦資源

**Python 相關**：

- [difflib 官方文檔](https://docs.python.org/3/library/difflib.html)
- [argparse 教學](https://docs.python.org/3/howto/argparse.html)
- [pathlib 指南](https://realpython.com/python-pathlib/)

**Vue.js 相關**：

- [Vue 3 官方文檔](https://vuejs.org/)
- [Vue 3 CDN 使用指南](https://vuejs.org/guide/quick-start.html#using-vue-from-cdn)
- [Vue 3 範例](https://vuejs.org/examples/)

**CSS 佈局**：

- [CSS Grid 完整指南](https://css-tricks.com/snippets/css/complete-guide-grid/)
- [Flexbox 完整指南](https://css-tricks.com/snippets/css/a-guide-to-flexbox/)

**工具**：

- [JSON Schema Validator](https://www.jsonschemavalidator.net/)
- [Can I Use](https://caniuse.com/) - 瀏覽器兼容性查詢

---

## 結語

這份文檔提供了 **Coverage Visualizer** 工具的完整實作規格。下一位開發者應該能夠根據這份文檔：

1. ✅ 理解專案的目標和需求
2. ✅ 了解系統的整體架構
3. ✅ 按照步驟完成 Python 分析器的開發
4. ✅ 按照步驟完成 Vue.js 前端的開發
5. ✅ 理解每個技術決策的原因
6. ✅ 處理常見問題和邊界情況
7. ✅ 考慮未來的擴展性

**預估開發時間**：

- **Python 分析器**：4-6 小時（包含測試）
- **Vue.js 前端**：6-8 小時（包含樣式和互動）
- **整合測試**：2-3 小時
- **總計**：12-17 小時

**開始實作前的檢查清單**：

- [ ] 已閱讀並理解本文檔的所有章節
- [ ] 已安裝 Python 3.11+
- [ ] 已準備好測試數據（原始文檔 + chunks 目錄）
- [ ] 已熟悉 Vue 3 基本語法
- [ ] 已了解 CSS Grid 和 Flexbox
- [ ] 已準備好開發環境（編輯器、瀏覽器）

**遇到問題時**：

1. 先查閱本文檔的相關章節
2. 查看第 11.4 節的常見問題
3. 檢查推薦資源中的官方文檔
4. 使用瀏覽器的 Developer Tools 調試

祝開發順利！🚀

---

**文檔版本**：1.0
**最後更新**：2025-10-31
**維護者**：Claude (AI Assistant)
