# sanhua-3d-calico-pet

A non-commercial, source-available 3D calico cat desktop pet package for Codex / Hatch Pet.

本项目是一个基于原创三花猫图像制作的 3D 桌面宠物包，包含可安装的宠物包、源帧、动画生成脚本、质量检查文件和预览材料。项目目标是提供一个可学习、可复现、可协作改进的 Codex 桌面宠物示例，同时明确保护原始猫咪图像、派生帧图、spritesheet 和最终宠物形象的版权。

> This project is not an official Codex, OpenAI, or Hatch Pet product. It is an independent personal desktop pet package.

---

## Project overview

This repository provides a repaired and stabilized 3D calico cat desktop pet.

The current pet package includes 9 animation states:

| State | Meaning |
|---|---|
| `idle` | Breathing, blinking, and subtle resting motion |
| `running-right` | Right-facing running animation |
| `running-left` | Left-facing running animation |
| `waving` | Small paw response |
| `jumping` | Crouch, takeoff, peak, fall, and landing |
| `failed` | Failed / relaxed side-lying motion |
| `waiting` | Waiting / stretching motion |
| `running` | Focused working micro-motion |
| `review` | Quiet observation / review pose |

The final Codex pet atlas uses:

```text
1536 x 1872 spritesheet
8 columns x 9 rows
192 x 208 px per frame
```

---

## Repository structure

```text
sanhua-3d-calico-pet/
├─ pet-package/
│  └─ sanhua-3d-calico-motionfix/
│     ├─ pet.json
│     └─ spritesheet.webp
│
├─ source_frames/
│  ├─ idle/
│  ├─ running-right/
│  ├─ running-left/
│  ├─ waving/
│  ├─ jumping/
│  ├─ failed/
│  ├─ waiting/
│  ├─ running/
│  └─ review/
│
├─ scripts/
│  ├─ motionfix_all_states_puppet.py
│  ├─ sync_build_to_package.ps1
│  └─ install_codex_pet.ps1
│
├─ qa/
│  ├─ validation.json
│  ├─ frame_stability_report.json
│  ├─ scale_comparison_summary.md
│  └─ other preview / QA records
│
├─ requirements.txt
├─ LICENSE-CODE.md
├─ LICENSE-ASSETS.md
├─ ASSET_LICENSE.md
└─ README.md
```

---

## What is included

This repository includes:

- the final installable desktop pet package;
- the final `spritesheet.webp`;
- the final `pet.json`;
- source animation frames;
- Python scripts used to rebuild the animation atlas;
- PowerShell scripts for syncing and local installation;
- QA records for validation, frame stability, and scale comparison.

The project is designed so that others can study how the pet package is produced, rather than only downloading a final image file.

---

## Installation for local use

### 1. Clone the repository

```bash
git clone https://github.com/forlabSUDA/sanhua-3d-calico-pet.git
cd sanhua-3d-calico-pet
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

The project currently requires:

```text
numpy
Pillow
scipy
```

### 3. Rebuild the pet package

On Windows PowerShell:

```powershell
python .\scripts\motionfix_all_states_puppet.py
```

This regenerates the build output, including the final atlas, preview files, validation records, and QA reports.

### 4. Sync build output into the installable package

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\sync_build_to_package.ps1
```

This copies the generated `pet.json` and `spritesheet.webp` into:

```text
pet-package/sanhua-3d-calico-motionfix/
```

### 5. Install the pet locally

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_codex_pet.ps1
```

The script installs the pet package into the local Codex pet directory:

```text
%USERPROFILE%\.codex\pets\sanhua-3d-calico-motionfix
```

Then open Codex settings and select:

```text
三花猫猫 3D 修复版
```

---

## Rebuilding workflow

The recommended development workflow is:

```text
source_frames/
    ↓
scripts/motionfix_all_states_puppet.py
    ↓
build/sanhua_3d_pet_motionfix_all/
    ↓
QA preview and validation
    ↓
scripts/sync_build_to_package.ps1
    ↓
pet-package/sanhua-3d-calico-motionfix/
    ↓
scripts/install_codex_pet.ps1
```

Please avoid manually editing the final `spritesheet.webp` unless necessary. The preferred workflow is to modify source frames or generation scripts, then rebuild the package so that the output remains reproducible.

---

## Quality control

The project includes QA records for checking whether the final animation package is structurally valid.

The QA process checks:

- spritesheet size;
- grid size;
- frame count;
- unused transparent cells;
- frame stability;
- scale consistency;
- crop risk;
- row-level normalization;
- animation state consistency.

The current validation target is:

```text
spritesheet size: 1536 x 1872
grid: 8 columns x 9 rows
cell size: 192 x 208
```

---

## Known limitations

This project focuses on visual animation and Codex pet packaging.

Current limitations:

- desktop movement behavior is not the main focus of this repository;
- click interaction support has not been fully confirmed;
- the current spritesheet is optimized for the standard Codex pet frame size, so very fine visual details may be reduced;
- the visual identity is intentionally kept stable rather than redesigned.

---

## Copyright

Copyright © 2026 forlabSUDA. All rights reserved unless explicitly permitted below.

The original cat images are fully owned by the project owner. The derived visual assets, source frames, animation frames, spritesheet, final pet package, and recognizable visual identity of the cat are also protected by copyright.

The cat image, spritesheet, animation frames, and final desktop pet appearance are not public-domain material. Public visibility of this repository does not mean that the visual assets may be used without conditions.

---

## License

This repository uses a dual-license model.

### Code

All source code, scripts, configuration files, package metadata, and documentation files are licensed under the GNU General Public License v3.0. See `LICENSE-CODE.md`.

This includes, but is not limited to:

- `scripts/`
- `.py` files
- `.ps1` files
- `requirements.txt`
- package metadata such as `pet.json`
- project documentation unless otherwise stated

### Visual assets

All original cat images, source frames, animation frames, spritesheets, preview images, QA preview images, contact sheets, GIF previews, and recognizable derivative visual assets are licensed under Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International. See `LICENSE-ASSETS.md`.

This includes, but is not limited to:

- `source_frames/`
- `spritesheet.webp`
- cat animation frames
- preview images
- contact sheets
- GIF previews
- the final recognizable calico cat desktop pet appearance

Commercial use of the visual assets is prohibited without explicit written permission from the copyright owner.

Any public derivative visual work must be non-commercial, must provide attribution, and must be shared under the same CC BY-NC-SA 4.0 terms.

---

## Permitted use

You may:

- download the project for personal desktop pet use;
- study the code, scripts, animation structure, and packaging workflow;
- modify the project for personal or educational use;
- submit issues or pull requests to improve this repository;
- create derivative versions only if they follow the same non-commercial and share-alike rules for visual assets.

You may not:

- sell this pet package or any derivative package;
- use the cat image, spritesheet, animation frames, or derivative visual assets in commercial products;
- use the cat image as a commercial mascot, brand asset, logo, merchandise design, NFT, paid sticker pack, paid desktop pet, paid app, advertising material, or paid design resource;
- repackage this project and distribute it as your own original work;
- remove copyright notices or attribution;
- claim ownership of the original cat image or derived visual identity;
- distribute a modified visual version without making the modified visual source files publicly available under the same non-commercial share-alike terms.

---

## Derivative works

Derivative visual works are allowed only under all of the following conditions:

1. The derivative work must be non-commercial.
2. The derivative work must clearly credit this repository.
3. The derivative work must keep the same CC BY-NC-SA 4.0 terms for visual assets.
4. The complete modified visual source files must be made publicly available.
5. The original cat image and visual identity must not be claimed as the derivative author's original creation.
6. Any modified pet package must clearly state that it is derived from this project.
7. Any public redistribution must include a link back to this repository.

A suggested attribution format is:

```text
Derived from sanhua-3d-calico-pet by forlabSUDA:
https://github.com/forlabSUDA/sanhua-3d-calico-pet
```

---

## Commercial use

Commercial use of the visual assets is prohibited without explicit written permission from the copyright owner.

Commercial use includes, but is not limited to:

- selling the pet package;
- selling modified versions;
- using the visual assets in paid software;
- using the cat image in a commercial brand or product;
- using the pet in advertising or promotional material;
- selling merchandise based on the cat image;
- using the image in NFT, blockchain, or paid collectible products;
- including the assets in paid templates, paid asset packs, or paid design resources;
- using the cat image, spritesheet, or animation frames as part of any monetized product or service.

For commercial permission requests, please contact the repository owner through GitHub.

---

## Contribution guidelines

Contributions are welcome if they respect the project license and visual identity.

Recommended contribution workflow:

1. Fork the repository.
2. Create a new branch.
3. Modify source frames or scripts.
4. Rebuild the pet package.
5. Check QA outputs.
6. Submit a pull request.

When submitting a pull request, please describe:

- which animation state was changed;
- whether the change affects motion, size, transparency, timing, or visual identity;
- whether the generation script was rerun;
- whether the QA files were checked;
- whether `validation.json` still passes.

Please do not submit changes that:

- replace the original cat identity with unrelated commercial assets;
- add copyrighted third-party images without permission;
- introduce private paths, account names, tokens, API keys, or personal files;
- remove copyright and license notices;
- change the project into a commercial asset package.

---

## Privacy and repository hygiene

Before committing changes, please check that no private local information is included.

Do not commit:

```text
.env
API keys
tokens
passwords
personal addresses
private emails
private screenshots
unpublished personal files
large temporary outputs
local absolute paths
```

Recommended checks before publishing:

```bash
git grep -n "token"
git grep -n "password"
git grep -n "api_key"
git grep -n "secret"
git grep -n "sk-"
git grep -n "Users"
git grep -n "E:\\"
git grep -n "C:\\"
```

If local paths appear in generated QA files, replace them with project-relative paths before publishing.

---

## Disclaimer

This project is provided as-is, without warranty of any kind.

The project owner is not responsible for damage, data loss, software conflicts, or other issues caused by local installation, modification, or redistribution.

Users and contributors are responsible for complying with this project's license terms and with applicable copyright laws.

---

## Attribution

If you use this project in a non-commercial demonstration, tutorial, or derivative project, please credit it as:

```text
sanhua-3d-calico-pet by forlabSUDA
https://github.com/forlabSUDA/sanhua-3d-calico-pet
```

---

## Contact

For issues, suggestions, or permission requests, please use GitHub Issues or contact the repository owner through GitHub.
