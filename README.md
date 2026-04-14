# Moyamoya Brain 🧠

**Moyamoya 病（毛毛樣腦血管疾病）每日文獻追蹤與 AI 分析**

## 簡介

本專案透過 GitHub Actions 每日自動執行以下流程：

1. **PubMed 搜尋** — 使用 14 組專業搜尋模板，涵蓋腦血管外科、神經影像、小兒神經、認知功能、復健醫學、物理治療、職能治療、語言治療等領域
2. **AI 分析** — 透過 Zhipu AI (GLM-5.1) 進行繁體中文摘要、PICO 分析、臨床實用性評估
3. **網頁生成** — 自動產生精美 HTML 日報，部署至 GitHub Pages

## 線上閱讀

🔗 [https://u8901006.github.io/moyamoya-brain/](https://u8901006.github.io/moyamoya-brain/)

## 搜尋範圍

搜尋模板涵蓋以下主題：

| 類別 | 搜尋內容 |
|------|---------|
| 廣泛搜尋 | moyamoya disease/syndrome/angiopathy + stroke/ischemia/perfusion |
| 外科手術 | revascularization, STA-MCA bypass, EDAS |
| 小兒神經 | pediatric + cognition/development/school/QoL |
| 成人認知 | adult + executive function/memory/attention |
| 神經精神 | depression/anxiety/behavior/emotional |
| 神經影像 | perfusion MRI/SPECT/PET/DTI/fMRI |
| 復健醫學 | rehabilitation/functional recovery/disability |
| 物理治療 | gait/balance/mobility/motor recovery |
| 職能治療 | ADL/IADL/participation/school function |
| 語言治療 | aphasia/dysarthria/dysphagia/swallowing |
| 生活品質 | QoL/return to school/work/caregiver |
| 認知恢復 | post-revascularization cognitive recovery |
| 長期追蹤 | longitudinal/prospective/cohort |
| 系統性回顧 | review/systematic review/meta-analysis |

## 技術架構

```
PubMed E-utilities API
        │
        ▼
  fetch_papers.py (14 search templates)
        │
        ▼
    papers.json
        │
        ▼
  generate_report.py (Zhipu AI GLM-5.1)
        │
        ▼
  docs/moyamoya-YYYY-MM-DD.html
        │
        ▼
  generate_index.py → docs/index.html
        │
        ▼
  GitHub Pages (auto deploy)
```

## 相關連結

- 🏥 [李政洋身心診所](https://www.leepsyclinic.com/)
- 📧 [訂閱電子報](https://blog.leepsyclinic.com/)
- 🔬 [Psychiatry Brain（精神醫學文獻日報）](https://github.com/u8901006/Psychiatry-brain)

## 授權

本專案為學術研究用途，文獻內容版權歸原作者所有。
