# Coverage Visualizer

視覺化 LLM chunk 提取的覆蓋率，確保無資訊遺漏。

## 快速開始

### 1. 生成分析報告

```bash
python tools/coverage_visualizer/analyzer.py \
  --document data/test/chapter_04_Depression_and_Suicidality.md \
  --chunks data/chunking_data_table_gemini_pro/chunks_claude_haiku/ \
  --output tools/coverage_visualizer/viewer/data/chapter_04_coverage.json
```

### 2. 啟動 Web 介面

```bash
cd tools/coverage_visualizer/viewer
python -m http.server 8000
```

### 3. 開啟瀏覽器

訪問：`http://localhost:8000`

## 專案結構

```
tools/coverage_visualizer/
├── analyzer.py              # Python 分析腳本
├── viewer/                  # Vue.js 前端介面
│   ├── index.html
│   ├── css/style.css
│   ├── js/app.js
│   └── data/               # 存放生成的 JSON
├── IMPLEMENTATION_SPEC.md   # 完整實作規格（500+ 行）
└── README.md               # 本文件
```

## 功能特性

- ✅ **模糊匹配**：使用 difflib 進行智能文本匹配
- ✅ **覆蓋率分析**：計算精確的覆蓋百分比
- ✅ **Gap 識別**：自動識別未覆蓋的內容（過濾小 gaps ≤5 字元）
- ✅ **互動視覺化**：點擊 chunk 即可在原文中高亮對應位置
- ✅ **顏色編碼**：綠色（高相似度）、黃色（中相似度）、橘色（低相似度）、灰色（gaps）
- ✅ **滾動同步**：左右欄位聯動滾動
- ✅ **閾值調整**：即時調整相似度閾值（80-100%）

## 參數說明

| 參數 | 必填 | 預設值 | 說明 |
|------|------|--------|------|
| `--document` | ✅ | - | 原始 Markdown 文檔路徑 |
| `--chunks` | ✅ | - | 包含 chunk JSON 的目錄路徑 |
| `--output` | ✅ | - | 輸出 JSON 報告的路徑 |
| `--threshold` | ❌ | 0.90 | 模糊匹配相似度閾值 (0.0-1.0) |

## 技術棧

- **後端**：Python 3.11+ (僅標準庫，無外部依賴)
- **前端**：Vue 3 (CDN)、純 CSS、Vanilla JavaScript
- **模糊匹配**：difflib.SequenceMatcher

## 輸出格式

生成的 JSON 包含：

```json
{
  "metadata": {
    "coverage_percentage": 98.5,
    "total_chunks": 51,
    "significant_gaps": 8
  },
  "original_text": "完整原文...",
  "chunks": [ /* 所有 chunks 的匹配結果 */ ],
  "gaps": [ /* 長度 > 5 的遺漏內容 */ ],
  "coverage_map": [ /* 細粒度的覆蓋狀態 */ ]
}
```

## 完整文檔

請參閱 [IMPLEMENTATION_SPEC.md](./IMPLEMENTATION_SPEC.md) 獲取：

- 詳細的系統架構說明
- 完整的 JSON Schema
- 逐步實作指南
- 技術決策說明
- 常見問題解答

**文檔長度**：~500 行 Markdown，涵蓋所有實作細節

## 使用場景

1. **驗證完整性**：確保 chunking 演算法未遺漏重要內容
2. **調試優化**：找出匹配失敗的原因並改進演算法
3. **質量保證**：定期檢查不同文檔的覆蓋率
4. **演示展示**：視覺化展示 chunk 提取結果

## 常見問題

**Q: 為什麼覆蓋率無法達到 100%？**

A: 可能原因：
- 文檔包含表格、圖片說明等特殊格式未被提取
- 存在小 gaps（≤5 字元），如空白行、標點符號
- 查看 `gaps` 列表確認遺漏的具體內容

**Q: 前端無法載入 JSON？**

A: 確保：
- 使用 `python -m http.server` 啟動伺服器（不要直接用 file:// 協議）
- JSON 文件路徑正確（放在 `viewer/data/` 目錄）
- 檢查瀏覽器 Console 的錯誤訊息

**Q: 如何調整匹配的嚴格程度？**

A:
- 使用 `--threshold` 參數調整（0.85-0.95 推薦）
- 或在前端介面中拖動滑桿即時調整

## 開發狀態

- [x] 實作規格文檔完成
- [ ] Python 分析器開發（待實作）
- [ ] Vue.js 前端開發（待實作）
- [ ] 整合測試（待實作）

## License

This tool is part of the langgraph project.
