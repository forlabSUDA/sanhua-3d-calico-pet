# 协作修改说明

这个项目建议用“小步修改、先看预览、再同步安装包”的方式协作。

## 推荐流程

1. 修改 `source_frames/` 里的某个状态帧，或修改 `scripts/motionfix_all_states_puppet.py` 的动作逻辑。
2. 运行：

```powershell
python ".\scripts\motionfix_all_states_puppet.py"
```

3. 查看：

```text
build/sanhua_3d_pet_motionfix_all/qa/contact-sheet.png
build/sanhua_3d_pet_motionfix_all/qa/previews/
build/sanhua_3d_pet_motionfix_all/qa/frame_stability_report.json
```

4. 如果确认可用，再运行：

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\sync_build_to_package.ps1"
```

5. 最后安装：

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\install_codex_pet.ps1"
```

## 不建议直接改的文件

不建议直接手动编辑：

```text
pet-package/sanhua-3d-calico-motionfix/spritesheet.webp
```

因为它是最终图集，直接改会失去每一帧的来源和 QA 记录。更推荐修改源帧或脚本后重新生成。

## 提交修改时请说明

提交或 PR 里最好写清楚：

- 改了哪个状态；
- 改的是动作、尺寸、透明背景还是花纹；
- 是否重新运行了生成脚本；
- 是否检查过 contact sheet 和 GIF；
- `validation.json` 是否仍然通过。

## 当前质量边界

Codex 标准宠物包使用 `192 x 208` 单帧，所以细节会比原始大图少。优化时优先保证：

- 完整全身；
- 不裁切耳朵、尾巴、爪子；
- 不忽大忽小；
- 动作语义清楚；
- 三花猫身份稳定。
