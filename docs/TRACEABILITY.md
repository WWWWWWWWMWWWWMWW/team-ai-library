# 来源、更新与复用追溯

## 下载与安装

下载记录真实 repository、shared_branch、完整 source_commit、ID/version、manifest 摘要和完整 dependency_lock。SHA 是取得真实提交后写入本地记录，不能预填，也不能回写进产生它自身的提交。

安装后本地 receipt 还记 target、baseline、实际 files 摘要、installed_at、local_changes。收据和原版基线放专用 workspace，不上传进能力目录。

baseline 始终是相应版本的上游原版；receipt.files 是实际安装内容。保留本地改动更新后，两者可能不同，必须明确。把混合候选存成基线，会使下一次更新误认本地改动为原版，所以禁止这样处理。

## 执行与改编

库流程使用前，通过 check-reuse 核对当前状态、实际根包和所有依赖、环境与任务范围。执行后本地 run record 最少记录：run_id、时间、每项来源、目标、实际环境、结果、产物位置、变更摘要、未验证项。

日志不默认包含完整聊天、原始业务输入或凭据，不自动上传。团队库提供方法；具体项目业务产物继续存本项目，不带着业务原始数据一起归档。

改编用 derived_from={repository,id,version,manifest_sha256,source_commit}，另记 changed_files/change_summary 与验证缺口。本地改编不继承原版身份或验证；用户明确要求共享时再提炼成新版本或新条目。

一个任务使用多项能力，记录每项来源。来源被应急清理后说明不可复现，引用替代版本但不能伪称原材料仍存在。
