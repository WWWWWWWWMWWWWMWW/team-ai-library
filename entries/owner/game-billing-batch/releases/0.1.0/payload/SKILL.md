---
name: game-billing-batch
description: Generate game billing-point batch import files for Huawei AGC, CN GM, and HMT/oversea GM backends from product IDs, Chinese names, and Cash prices. Use when the user asks to add, batch-create, import, or prepare game payment goods/计费点/礼包计费点 across 华为、国服、港澳台后台, especially with .xlsx Huawei exports or GM goods .csv files.
---

# Game Billing Batch

## Core Rule

Create import files from existing backend exports. Do not calculate exchange rates manually and do not edit live backend pages unless the user explicitly asks.

For each new product, use only `ProductId/物品ID`, Chinese name, and `Cash:<fen>` price from the user. Preserve all other fields by copying the same-price reference row from the relevant backend export.

## Backend Mapping

- Huawei AGC: output `.xlsx`. Use an existing Huawei export row with the same `CN` price. The verified `full` mode preserves the entire 183-country price mapping and moves `CN;<CNY price>` to the first pair. The trial `cn-only` mode writes only `CN;<CNY price>` while preserving the sales scope so Huawei can fill missing countries at creation time. Do not make `cn-only` the default until a real backend import confirms the behavior.
- CN GM: output `.csv`. Use the latest existing row with the same `物品金额（分）`; copy payment template fields such as 微信小游戏、苹果 APP、微信小游戏道具支付, then replace ID/name and clear `创建时间`.
- HMT/oversea GM: output `.csv`. Use the latest existing row with the same `物品金额（分）`; normally 1800 maps to Apple/Google `m18`, 6800 to `m68`, 9800 to `m98`, 32800 to `m328`. Prefer copying from export instead of hardcoding.

## Workflow

1. Identify the newest suitable exports in Downloads unless the user provides exact paths:
   - Huawei: `AGC_C*_PMS_*.xlsx`
   - CN GM: `goods_fejsfmerge_mix*.csv`
   - HMT GM: `goods_fejsf_oversea*.csv`
2. Parse the user product list. Accept rows like `777026 镜中迷踪 Cash:1800` or tab-separated `777026\t镜中迷踪\tCash:1800`.
3. Check every target ID against all supplied exports. If an ID already exists, stop and report which backend has it; do not generate an import file that would modify existing计费点 unless the user explicitly confirms overwrite/update.
4. Generate three files under the current task's `outputs/` directory, named clearly by backend and ID range.
5. Verify:
   - Row count equals requested product count.
   - All IDs/names/prices match the request.
   - Huawei `Price` has even country/price tokens and starts with `CN;<amount/100 with 2 decimals>`.
   - Huawei `full` mode price pair count should match the reference row, commonly 183; `cn-only` mode must contain exactly one pair.
   - GM CSV payment fields match the copied same-price template.
6. Final response should link only the final three files and state the key verification result.

## Script

Use `scripts/generate_billing_batches.py` for repeatable generation.

Example:

```bash
python3 /Users/hcm-b0263/.codex/skills/game-billing-batch/scripts/generate_billing_batches.py \
  --products "777026	镜中迷踪	Cash:1800" \
  --huawei-export /Users/hcm-b0263/Downloads/AGC_C107049929_PMS_20260731102920.xlsx \
  --cn-export "/Users/hcm-b0263/Downloads/goods_fejsfmerge_mix (31).csv" \
  --hmt-export "/Users/hcm-b0263/Downloads/goods_fejsf_oversea (27).csv" \
  --output-dir /Users/hcm-b0263/Documents/Codex/2026-06-18/new-chat/outputs
```

For multiple products, pass `--products-file` with one product per line.

For a controlled Huawei current-rate trial, add `--huawei-price-mode cn-only`. Existing product IDs are batch modifications, so they do not prove the missing-country autofill behavior used when creating a new product.

## Safety Notes

- Never touch unrelated existing billing points.
- Do not import a Huawei creation file whose `Price` starts with `AD` or another country. Huawei exports may sort prices with `AD` first even when the product was manually created from a CNY base; move the existing `CN` pair to the front before reusing the row for a new product.
- Treat Huawei `Status=0` as active in batch files; after importing in the Huawei backend, the user may still need to confirm activation in the UI if the backend requires it.
- If a requested Cash price has no same-price reference in an export, stop and ask for a backend export containing that price or explicit instructions for creating a new price template.
